"""Paytm AI ActionMate Phase 5 Safety, Governance & Audit Test Suite.
Validates:
1. Action Risk Policy 3-tier categorization (Category A, B, C).
2. Autonomous AI strictly blocked from Category C financial operations (refunds, bank mutations).
3. Human approval requirement: unapproved campaigns strictly cannot execute.
4. Unauthorized approvers rejected with PolicyViolationError / HTTP 403.
5. Message or offer edits immediately invalidate prior approvals.
6. Execution strictly blocked after message edit without fresh re-approval.
7. Rejected campaigns cannot execute.
8. Paused campaigns cannot execute; resuming restores execution capability.
9. Duplicate execution prevention & strict idempotency enforcement.
10. Cryptographic SHA-256 tamper-evident audit ledger verification.
"""

import io
import json
import unittest
from backend.app.database import init_db, get_connection
from backend.app.services.campaign_service import CampaignService
from backend.app.services.governance_service import (
    GovernanceService,
    PolicyViolationError,
    ApprovalPreconditionError,
    ContentDriftError,
    CATEGORY_A,
    CATEGORY_B,
    CATEGORY_C,
    ACTION_RISK_MAP
)
from backend.app.services.audit_service import AuditService
from backend.app.services.simulated_execution_adapter import (
    SimulatedCampaignExecutionAdapter,
    DuplicateExecutionError,
    ExecutionAdapterError
)
from backend.app.orchestrator import registry
from backend.app.server import DealPilotRequestHandler

class MockServer:
    server_address = ("127.0.0.1", 8000)

class DummyHandler(DealPilotRequestHandler):
    def __init__(self, path, method="GET", body=b""):
        self.requestline = f"{method} {path} HTTP/1.1"
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.headers = {"Content-Length": str(len(body)), "Content-Type": "application/json"}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.client_address = ("127.0.0.1", 54321)
        self.server = MockServer()
        if method == "GET":
            self.do_GET()
        elif method == "POST":
            self.do_POST()

def get_response_data(handler):
    raw = handler.wfile.getvalue()
    if b"\r\n\r\n" in raw:
        body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8")
    elif b"\n\n" in raw:
        body = raw.split(b"\n\n", 1)[1].decode("utf-8")
    else:
        body = raw.decode("utf-8")
    return json.loads(body)

def get_status_code(handler):
    raw = handler.wfile.getvalue()
    first_line = raw.split(b"\r\n")[0].decode("utf-8", errors="ignore")
    parts = first_line.split(" ")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 200

class TestSafetyAndGovernancePhase5(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        """Cleans up test artifacts to guarantee test isolation."""
        conn = get_connection()
        cur = conn.cursor()
        test_ids = [
            "CAMP-GOV-UNAPPR-01",
            "CAMP-GOV-AUTH-02",
            "CAMP-GOV-EDIT-03",
            "CAMP-GOV-REJ-04",
            "CAMP-GOV-PAUSE-05",
            "CAMP-GOV-IDEMP-06"
        ]
        placeholders = ",".join(["?"] * len(test_ids))
        cur.execute(f"DELETE FROM approvals WHERE campaign_id IN ({placeholders})", test_ids)
        cur.execute(f"DELETE FROM campaign_recipient_statuses WHERE campaign_id IN ({placeholders})", test_ids)
        cur.execute(f"DELETE FROM campaign_activity_timeline WHERE campaign_id IN ({placeholders})", test_ids)
        cur.execute(f"DELETE FROM campaign_drafts WHERE campaign_id IN ({placeholders})", test_ids)
        conn.commit()
        conn.close()

    def test_01_action_risk_policy_categories(self):
        """Validates 3-category action risk policy definitions and evaluation logic."""
        # Category A: Automatic actions
        cat_a_actions = ["get_sales_summary", "get_customer_segments", "recommend_campaign", "create_campaign_draft"]
        for act in cat_a_actions:
            self.assertEqual(ACTION_RISK_MAP.get(act), CATEGORY_A)
            eval_res = GovernanceService.evaluate_action_policy(act)
            self.assertEqual(eval_res.category, CATEGORY_A)
            self.assertTrue(eval_res.allowed)
            self.assertFalse(eval_res.requires_human_approval)

        # Category B: Human approval required
        cat_b_actions = ["execute_demo_campaign", "send_customer_message", "broadcast_soundbox_voice"]
        for act in cat_b_actions:
            self.assertEqual(ACTION_RISK_MAP.get(act), CATEGORY_B)
            # Without approval -> blocked
            unappr_res = GovernanceService.evaluate_action_policy(act, has_approval=False)
            self.assertEqual(unappr_res.category, CATEGORY_B)
            self.assertFalse(unappr_res.allowed)
            self.assertTrue(unappr_res.requires_human_approval)
            # With approval -> allowed
            appr_res = GovernanceService.evaluate_action_policy(act, has_approval=True)
            self.assertTrue(appr_res.allowed)

        # Category C: Human-Only / Financial operations (Strictly Blocked for Autonomous AI)
        cat_c_actions = ["issue_refund", "modify_bank_account", "change_settlement_schedule"]
        for act in cat_c_actions:
            self.assertEqual(ACTION_RISK_MAP.get(act), CATEGORY_C)
            cat_c_eval = GovernanceService.evaluate_action_policy(act)
            self.assertEqual(cat_c_eval.category, CATEGORY_C)
            self.assertFalse(cat_c_eval.allowed)
            self.assertTrue(cat_c_eval.is_financial_mutation)
            self.assertIn("FINANCIAL_ACTION_BLOCKED", cat_c_eval.reason)

    def test_02_category_c_financial_actions_strictly_blocked(self):
        """Verifies autonomous AI is blocked from executing Category C financial mutations in Tool Registry."""
        # Test issue_refund tool call
        refund_res = registry.execute(
            "issue_refund",
            {"order_id": "ORD-DEMO-999", "amount_inr": 450.0, "reason": "Customer complaint"}
        )
        self.assertEqual(refund_res.status, "FAILED")
        self.assertIn("FINANCIAL_ACTION_BLOCKED", refund_res.error_message)
        self.assertFalse(refund_res.verified)

        # Test modify_bank_account tool call
        bank_res = registry.execute(
            "modify_bank_account",
            {"account_number": "987654321012", "ifsc_code": "PYTM0123456"}
        )
        self.assertEqual(bank_res.status, "FAILED")
        self.assertIn("FINANCIAL_ACTION_BLOCKED", bank_res.error_message)

        # Check audit log contains FINANCIAL_ACTION_BLOCKED event
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT action_type, tool_name FROM audit_trail WHERE action_type = 'FINANCIAL_ACTION_BLOCKED' ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["action_type"], "FINANCIAL_ACTION_BLOCKED")

    def test_03_unapproved_campaign_cannot_execute(self):
        """Verifies unapproved campaign drafts strictly fail pre-execution checks and execution adapter dispatches."""
        cid = "CAMP-GOV-UNAPPR-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Unapproved Test Campaign",
            "business_objective": "Test Gate Enforcement",
            "reason_for_recommendation": "Testing unapproved execution blockage",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })

        # Precondition check must fail
        with self.assertRaises(ApprovalPreconditionError) as ctx:
            GovernanceService.verify_execution_preconditions(cid)
        self.assertIn("Precondition 1 Failed", str(ctx.exception))
        self.assertIn("No human approval record exists", str(ctx.exception))

        # Simulated execution adapter must fail
        with self.assertRaises((ApprovalPreconditionError, ExecutionAdapterError)):
            SimulatedCampaignExecutionAdapter.execute_campaign(cid)

    def test_04_unauthorized_approver_rejected(self):
        """Verifies approvals by unauthorized users are rejected via service and HTTP endpoint."""
        cid = "CAMP-GOV-AUTH-02"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Authorization Test Campaign",
            "business_objective": "Test Unauthorized Sign-off",
            "reason_for_recommendation": "Security test",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })

        # Direct service call with rogue user
        with self.assertRaises(PolicyViolationError) as ctx:
            GovernanceService.approve_campaign(cid, approver_id="ROGUE-USER-999")
        self.assertIn("UNAUTHORIZED_APPROVER", str(ctx.exception))

        # HTTP API call with unauthorized approver
        body = json.dumps({"approver_id": "UNKNOWN-ATTACKER", "max_budget_authorized": 5000.0}).encode("utf-8")
        handler = DummyHandler(f"/api/approvals/{cid}/approve", method="POST", body=body)
        status_code = get_status_code(handler)
        resp_data = get_response_data(handler)
        self.assertEqual(status_code, 403)
        self.assertEqual(resp_data.get("code"), "UNAUTHORIZED_APPROVER")

    def test_05_message_edit_invalidates_approval(self):
        """Verifies editing campaign copy or offer immediately invalidates prior approvals and updates state."""
        cid = "CAMP-GOV-EDIT-03"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Drift Invalidation Campaign",
            "business_objective": "Test Auto Invalidation",
            "reason_for_recommendation": "Testing content drift security",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })

        # Step 1: Approve draft with authorized approver
        appr_rec = GovernanceService.approve_campaign(cid, approver_id="USER-001")
        self.assertEqual(appr_rec.decision, "APPROVED")
        self.assertEqual(appr_rec.approval_status, "VALID")

        # Verify DB has valid approval
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT approval_status FROM approvals WHERE campaign_id = ?", (cid,))
        row = cur.fetchone()
        self.assertEqual(row["approval_status"], "VALID")
        conn.close()

        # Step 2: Edit campaign copy
        edit_res = GovernanceService.edit_campaign(
            cid,
            editor_id="USER-001",
            new_en_message="Modified message: 60% off everything today only!"
        )
        self.assertEqual(edit_res["status"], "PENDING_APPROVAL")
        self.assertEqual(edit_res["approval_status"], "INVALIDATED")

        # Step 3: Verify prior approval is now INVALIDATED in the database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT approval_status, reason_or_comments FROM approvals WHERE campaign_id = ?", (cid,))
        appr_row = cur.fetchone()
        conn.close()
        self.assertEqual(appr_row["approval_status"], "INVALIDATED")
        self.assertIn("invalidated", appr_row["reason_or_comments"].lower())

    def test_06_execution_blocked_after_message_edit_without_reapproval(self):
        """Verifies execution is strictly blocked after edit until fresh approval is granted."""
        cid = "CAMP-GOV-EDIT-03"  # Continues from test_05 setup or re-creates
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Re-approval Test Campaign",
            "business_objective": "Test Re-approval Workflow",
            "reason_for_recommendation": "Testing blocked execution",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        GovernanceService.edit_campaign(cid, editor_id="USER-001", new_en_message="Altered text")

        # Execution must fail because approval was invalidated
        with self.assertRaises(ApprovalPreconditionError) as ctx:
            GovernanceService.verify_execution_preconditions(cid)
        self.assertIn("Precondition 1 Failed", str(ctx.exception))
        self.assertIn("INVALIDATED", str(ctx.exception))

        # Re-approve campaign
        fresh_appr = GovernanceService.approve_campaign(cid, approver_id="USER-001", comments="Re-approved after copy review")
        self.assertEqual(fresh_appr.approval_status, "VALID")

        # Execution preconditions must now pass cleanly
        verify_res = GovernanceService.verify_execution_preconditions(cid)
        self.assertTrue(verify_res["verified"])
        self.assertEqual(verify_res["campaign_id"], cid)

    def test_07_rejected_campaign_cannot_execute(self):
        """Verifies rejected campaign cannot be executed under any circumstances."""
        cid = "CAMP-GOV-REJ-04"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Rejection Test Campaign",
            "business_objective": "Test Rejection Enforcement",
            "reason_for_recommendation": "Security test",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })

        # Reject campaign
        rej_res = GovernanceService.reject_campaign(cid, approver_id="USER-001", reason="Margin impact too high.")
        self.assertEqual(rej_res["status"], "REJECTED")

        # Verification must fail Precondition 5
        with self.assertRaises(ApprovalPreconditionError) as ctx:
            GovernanceService.verify_execution_preconditions(cid)
        self.assertIn("Precondition 5 Failed", str(ctx.exception))
        self.assertIn("REJECTED", str(ctx.exception))

    def test_08_paused_and_resumed_campaign_lifecycle(self):
        """Verifies paused campaigns cannot execute, and resuming restores execution capability."""
        cid = "CAMP-GOV-PAUSE-05"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Pause Resume Lifecycle Campaign",
            "business_objective": "Test Lifecycle Controls",
            "reason_for_recommendation": "Testing pause/resume gates",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")

        # Pause task
        pause_res = GovernanceService.pause_task(cid, actor="Ramesh Sharma", reason="Store closed for stock audit")
        self.assertEqual(pause_res["status"], "PAUSED")

        # Verification must fail while paused
        with self.assertRaises(ApprovalPreconditionError) as ctx:
            GovernanceService.verify_execution_preconditions(cid)
        self.assertIn("Precondition 5 Failed", str(ctx.exception))
        self.assertIn("PAUSED", str(ctx.exception))

        # Resume task
        resume_res = GovernanceService.resume_task(cid, actor="Ramesh Sharma")
        self.assertEqual(resume_res["status"], "APPROVED")

        # Verification must now pass
        v_res = GovernanceService.verify_execution_preconditions(cid)
        self.assertTrue(v_res["verified"])

    def test_09_duplicate_execution_prevention_idempotency(self):
        """Verifies duplicate execution attempts of a completed campaign are strictly rejected (Precondition 6)."""
        cid = "CAMP-GOV-IDEMP-06"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Idempotency Test Campaign",
            "business_objective": "Test Duplicate Prevention",
            "reason_for_recommendation": "Testing execution idempotency",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")

        # First execution succeeds
        exec_res = SimulatedCampaignExecutionAdapter.execute_campaign(cid, caller="IdempotencyTest")
        self.assertEqual(exec_res.status, "COMPLETED")
        self.assertTrue(exec_res.is_demo)

        # Second execution must raise DuplicateExecutionError or ApprovalPreconditionError
        with self.assertRaises(ApprovalPreconditionError) as ctx:
            GovernanceService.verify_execution_preconditions(cid)
        self.assertIn("Precondition 6 Failed", str(ctx.exception))
        self.assertIn("Idempotency", str(ctx.exception))

        with self.assertRaises((DuplicateExecutionError, ApprovalPreconditionError)):
            SimulatedCampaignExecutionAdapter.execute_campaign(cid, caller="IdempotencyTest")

    def test_10_cryptographic_audit_ledger_tamper_evidence(self):
        """Verifies SHA-256 chained audit ledger integrity and tamper detection."""
        # Step 1: Ensure clean ledger verification passes
        clean_res = AuditService.verify_ledger_integrity()
        self.assertTrue(clean_res["valid"], f"Initial audit ledger verification failed: {clean_res}")
        self.assertGreater(clean_res["blocks_verified"], 0)

        # Step 2: Tamper with a block payload in the database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, action_type FROM audit_trail ORDER BY id DESC LIMIT 1")
        target_block = cur.fetchone()
        self.assertIsNotNone(target_block)
        block_id = target_block["id"]
        original_action = target_block["action_type"]

        # Inject unauthorized payload mutation
        cur.execute("UPDATE audit_trail SET action_type = 'UNAUTHORIZED_MUTATION_HACK' WHERE id = ?", (block_id,))
        conn.commit()
        conn.close()

        # Step 3: Cryptographic verification must immediately detect tampering
        tamper_res = AuditService.verify_ledger_integrity()
        self.assertFalse(tamper_res["valid"])
        self.assertEqual(tamper_res["tampered_block_id"], block_id)
        self.assertIn("Tampering detected", tamper_res["error"])

        # Step 4: Restore block and verify integrity is restored
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE audit_trail SET action_type = ? WHERE id = ?", (original_action, block_id))
        conn.commit()
        conn.close()

        restored_res = AuditService.verify_ledger_integrity()
        self.assertTrue(restored_res["valid"])

if __name__ == "__main__":
    unittest.main()
