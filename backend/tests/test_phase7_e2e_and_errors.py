"""Paytm AI ActionMate Phase 7 End-to-End Verification & Boundary Test Suite.
Validates:
1. Complete 20-Step End-to-End Presentation Workflow:
   Prompt -> Intent -> Context -> Sales -> Analysis -> Repeat Trend ->
   Recommendation -> Targeting -> Indic Copy -> Rationale -> Approval Request ->
   Review -> HMAC Approval -> Dispatch -> Logs -> 7-Point Verification ->
   Status Update -> Chained Audit Ledger -> KPIs -> Completion Report.
2. 15 Comprehensive Error & Boundary Scenarios covering edge cases, safety invariants,
   fault tolerance, and demo isolation.
"""

import io
import json
import sqlite3
import unittest
from backend.app.database import init_db, get_connection
from backend.app.config import DB_PATH
from backend.app.schemas import TaskSchema
from backend.app.orchestrator import (
    orchestrator, registry, IntentAnalyzer, ReasoningEngine, TaskPlanner,
    STATE_READY_FOR_APPROVAL, STATE_COMPLETED, STATE_VERIFYING
)
from backend.app.services.sales_intelligence_service import (
    get_merchant_profile,
    calculate_sales_summary,
    calculate_repeat_analysis,
    detect_sales_drop
)
from backend.app.services.campaign_service import CampaignService
from backend.app.services.governance_service import (
    GovernanceService,
    PolicyViolationError,
    ApprovalPreconditionError,
    ContentDriftError,
    CATEGORY_A,
    CATEGORY_B,
    CATEGORY_C
)
from backend.app.services.simulated_execution_adapter import (
    SimulatedCampaignExecutionAdapter,
    DuplicateExecutionError,
    ExecutionAdapterError
)
from backend.app.services.verification_service import VerificationService
from backend.app.services.failure_recovery_service import FailureRecoveryService, RecoveryError
from backend.app.services.kpi_service import KPIService
from backend.app.services.reporting_service import TaskReportingService
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


class TestPhase7E2EAndErrorBoundaries(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        conn = get_connection()
        cur = conn.cursor()
        test_cids = [
            "CAMP-E2E-P7-01",
            "CAMP-REJECT-P7-01",
            "CAMP-DRIFT-P7-01",
            "CAMP-IDEMP-P7-01",
            "CAMP-VFAIL-P7-01",
            "CAMP-AUTH-P7-01",
            "CAMP-FAIL-REC-01"
        ]
        test_tids = ["TASK-E2E-P7-01", "TASK-FAIL-P7-01"]
        c_placeholders = ",".join(["?"] * len(test_cids))
        t_placeholders = ",".join(["?"] * len(test_tids))
        cur.execute(f"DELETE FROM verifications WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM task_escalations WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM campaign_recipient_statuses WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM campaign_activity_timeline WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM campaign_drafts WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM approvals WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM task_state_history WHERE task_id IN ({t_placeholders})", test_tids)
        cur.execute(f"DELETE FROM tasks WHERE task_id IN ({t_placeholders})", test_tids)
        conn.commit()
        conn.close()

    # =========================================================================
    # 20-Step End-to-End Presentation Workflow
    # =========================================================================

    def test_01_complete_20_step_e2e_presentation_journey(self):
        """
        Executes the exact 20-step merchant workflow from PPT:
        Prompt: 'My sales have dropped this week. Help me bring customers back.'
        """
        merchant_id = "MERCH-001"
        task_id = "TASK-E2E-P7-01"
        cid = "CAMP-E2E-P7-01"
        user_prompt = "My sales have dropped this week. Help me bring customers back."

        # Step 1: Submit request & Step 2: Understand intent
        intent_data = IntentAnalyzer.analyze_request(user_prompt, merchant_id=merchant_id)
        self.assertEqual(intent_data["detected_intent"], "SALES_RECOVERY_REENGAGEMENT")
        self.assertEqual(intent_data["risk_classification"], "MEDIUM")
        self.assertTrue(intent_data["approval_requirements"]["requires_merchant_approval"])

        # Step 3: Retrieve business context
        profile = get_merchant_profile(merchant_id)
        self.assertEqual(profile.store_name, "Sharma Commercial & Industrial Supplies")
        self.assertEqual(profile.city, "Connaught Place, New Delhi")

        # Step 4: Retrieve weekly sales & Step 5: Analyse sales trend
        sales_summary = calculate_sales_summary(merchant_id)
        self.assertEqual(sales_summary.last_week_total_k, 412.0)
        self.assertEqual(sales_summary.this_week_total_k, 300.0)
        self.assertEqual(sales_summary.overall_drop_pct, -27.2)

        drop_info = detect_sales_drop(merchant_id)
        self.assertTrue(drop_info.is_drop_detected)
        self.assertEqual(drop_info.sales_difference_inr, 112000.0)

        # Step 6: Detect declining repeat purchases
        repeat_info = calculate_repeat_analysis(merchant_id)
        self.assertEqual(repeat_info.week_1_pct, 41.0)
        self.assertEqual(repeat_info.week_4_pct, 24.0)
        self.assertEqual(repeat_info.drop_percentage_points, -13.0)

        # Step 7: Recommend re-engagement campaign
        rec = CampaignService.recommend_campaign_for_sales_drop(merchant_id)
        self.assertIn("Recovery Campaign", rec.campaign_name)
        self.assertEqual(rec.offer_details["discount_code"], "RET50")
        self.assertEqual(rec.offer_details["discount_amount_inr"], 50.0)

        # Step 8: Identify eligible customers (Audience Targeting)
        audience = CampaignService.evaluate_campaign_audience(merchant_id, "DECLINING_FREQUENCY")
        self.assertEqual(audience.total_evaluated, 46)
        self.assertEqual(audience.excluded_count, 1)
        self.assertEqual(audience.eligible_count, 45)

        # Step 9: Personalised promotional copy (EN, HI, Soundbox)
        sample_cust = audience.eligible_customers[0]
        rendered_msg = CampaignService.render_personalized_message(
            sample_cust,
            profile.store_name,
            rec.offer_details
        )
        self.assertIn("RET50", rendered_msg.body_en)
        self.assertIn("₹50", rendered_msg.body_en)
        self.assertIn("RET50", rendered_msg.body_hi)
        self.assertIn("RET50", rendered_msg.soundbox_voice_prompt)

        # Step 10: Rationale explanation
        self.assertIn("repeat", rec.reason_for_recommendation.lower())
        self.assertIn("24%", rec.reason_for_recommendation)

        # Step 11: Request merchant approval (Create Draft)
        draft = CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": merchant_id,
            "campaign_name": rec.campaign_name,
            "business_objective": rec.business_objective,
            "reason_for_recommendation": rec.reason_for_recommendation,
            "target_customer_segment": rec.target_customer_segment,
            "suggested_duration": rec.suggested_campaign_duration,
            "recommended_channels": rec.recommended_communication_channel,
            "offer_configured": True,
            "offer_details": rec.offer_details,
            "message_en": rendered_msg.body_en,
            "message_hi": rendered_msg.body_hi,
            "soundbox_prompt": rendered_msg.soundbox_voice_prompt,
            "task_id": task_id
        })
        self.assertEqual(draft.status, "DRAFT")

        # Step 12: Merchant reviews message & Step 13: Merchant approves campaign
        appr_rec = GovernanceService.approve_campaign(
            campaign_id=cid,
            approver_id="USER-001",
            comments="Authorized for repeat customer reactivation."
        )
        self.assertEqual(appr_rec.decision, "APPROVED")
        self.assertEqual(appr_rec.approval_status, "VALID")
        self.assertTrue(len(appr_rec.content_hash) == 64)

        # Step 14: Simulated execution starts & Step 15: Execution adapter records results
        exec_res = SimulatedCampaignExecutionAdapter.execute_campaign(cid)
        self.assertEqual(exec_res.status, "COMPLETED")
        self.assertEqual(exec_res.total_attempted, 97)
        self.assertGreater(exec_res.delivered_count, 0)
        self.assertTrue(exec_res.execution_id.startswith("EXEC-"))

        # Step 16: Verification engine checks the execution (7-point audit)
        v_res = VerificationService.verify_campaign_execution(cid, task_id=task_id)
        self.assertEqual(v_res.verification_status, "VERIFIED")
        self.assertEqual(len(v_res.verified_checks), 7)
        self.assertEqual(len(v_res.failed_checks), 0)

        # Step 17: Task status is updated
        task = orchestrator.create_task_from_request(user_prompt, merchant_id=merchant_id, task_id=task_id)
        self.assertEqual(task.current_state, STATE_READY_FOR_APPROVAL)

        # Step 18: Audit log records complete journey (chained hashes)
        from backend.app.services.audit_service import AuditService
        ledger_res = AuditService.verify_ledger_integrity()
        self.assertTrue(ledger_res["valid"])
        self.assertGreater(ledger_res["blocks_verified"], 0)

        # Step 19: KPI analytics updated
        kpi_res = KPIService.calculate_kpis(merchant_id)
        self.assertTrue(kpi_res["has_data"])
        self.assertIn("task_completion_rate", kpi_res["kpis"])

        # Step 20: Completion report & export
        report_res = TaskReportingService.generate_task_report(task_id)
        md_text = TaskReportingService.export_report_markdown(task_id)
        self.assertIn("Executive Task Audit Report", md_text)
        self.assertEqual(report_res.verification_result.get("status"), "VERIFIED")

    # =========================================================================
    # 15 Boundary and Error Matrix Scenarios
    # =========================================================================

    def test_02_empty_sales_data_handling(self):
        """Scenario 1: Non-existent merchant returns 0s gracefully without crash."""
        res = calculate_sales_summary("MERCH-NON-EXISTENT")
        self.assertEqual(res.last_week_total_k, 0.0)
        self.assertEqual(res.this_week_total_k, 0.0)
        self.assertEqual(res.overall_drop_pct, 0.0)

    def test_03_missing_previous_period_comparison(self):
        """Scenario 2: Gracefully handles missing period comparison."""
        drop = detect_sales_drop("MERCH-EMPTY-001")
        self.assertFalse(drop.is_drop_detected)
        self.assertEqual(drop.sales_difference_inr, 0.0)

    def test_04_zero_repeat_customers_condition(self):
        """Scenario 3: Zero repeat customers avoids division-by-zero."""
        rep = calculate_repeat_analysis("MERCH-EMPTY-001")
        self.assertEqual(rep.week_1_pct, 0.0)
        self.assertEqual(rep.drop_percentage_points, 0.0)

    def test_05_zero_eligible_audience(self):
        """Scenario 4: Gracefully handles empty audience matching."""
        aud = CampaignService.evaluate_campaign_audience("MERCH-EMPTY-001", "ALL")
        self.assertEqual(aud.eligible_count, 0)
        self.assertEqual(len(aud.eligible_customers), 0)

    def test_06_invalid_customer_exclusions(self):
        """Scenario 5: DND and invalid contact details are deterministically filtered."""
        aud = CampaignService.evaluate_campaign_audience("MERCH-001", "ALL")
        self.assertEqual(aud.excluded_count, 3)
        excl_reasons = {c["customer_id"]: c["reason"] for c in aud.excluded_customers}
        self.assertEqual(excl_reasons["CUST-1045"], "OPTED_OUT_UNSUBSCRIBED")
        self.assertEqual(excl_reasons["CUST-1046"], "INVALID_EMAIL_ADDRESS")
        self.assertEqual(excl_reasons["CUST-1047"], "INVALID_PHONE_NUMBER")

    def test_07_offline_llm_fallback(self):
        """Scenario 6: Deterministic reasoning engine acts as zero-failure offline fallback."""
        intent = IntentAnalyzer.analyze_request("My sales have dropped this week.", merchant_id="MERCH-001")
        self.assertEqual(intent["provider"], "DETERMINISTIC_REASONING_ENGINE")
        self.assertEqual(intent["detected_intent"], "SALES_RECOVERY_REENGAGEMENT")

    def test_08_tool_execution_failure_handling(self):
        """Scenario 7: Simulates failure diagnostics and human escalation."""
        cid = "CAMP-FAIL-REC-01"
        tid = "TASK-FAIL-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Failure Recovery Test",
            "business_objective": "Test Failure",
            "reason_for_recommendation": "Testing recovery",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        esc_res = FailureRecoveryService.escalate_to_human(
            task_id=tid,
            campaign_id=cid,
            reason="SMS Provider socket timeout after retry cap",
            suggested_action="Review gateway connection and execute manually."
        )
        self.assertIn(esc_res["status"], ["ESCALATED", "ESCALATED_TO_HUMAN"])

        diag = FailureRecoveryService.evaluate_failure(cid, tid)
        self.assertEqual(diag.failure_type, "ESCALATED_TO_HUMAN")
        self.assertFalse(diag.can_retry)

    def test_09_approval_rejection_workflow(self):
        """Scenario 8: Rejection cancels draft and blocks execution."""
        cid = "CAMP-REJECT-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Rejection Test Campaign",
            "business_objective": "Test Rejection",
            "reason_for_recommendation": "Testing rejection flow",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        rej_res = GovernanceService.reject_campaign(cid, approver_id="USER-001", reason="Margin too low.")
        self.assertEqual(rej_res["status"], "REJECTED")

        # Execution must fail
        with self.assertRaises((ApprovalPreconditionError, ExecutionAdapterError)):
            SimulatedCampaignExecutionAdapter.execute_campaign(cid)

    def test_10_post_approval_copy_drift_invalidation(self):
        """Scenario 9: Editing message content post-approval invalidates token."""
        cid = "CAMP-DRIFT-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Drift Invalidation Campaign",
            "business_objective": "Test Tamper Security",
            "reason_for_recommendation": "Testing hash verification",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")

        # Edit campaign copy using GovernanceService
        GovernanceService.edit_campaign(cid, editor_id="USER-001", new_en_message="Tampered message body")

        with self.assertRaises((ContentDriftError, ApprovalPreconditionError)):
            GovernanceService.verify_execution_preconditions(cid)

    def test_11_duplicate_execution_idempotency(self):
        """Scenario 10: Executing the same campaign twice raises DuplicateExecutionError."""
        cid = "CAMP-IDEMP-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Idempotency Test Campaign",
            "business_objective": "Test Duplicate Block",
            "reason_for_recommendation": "Testing idempotency",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        SimulatedCampaignExecutionAdapter.execute_campaign(cid)

        # Second execution must fail
        with self.assertRaises(DuplicateExecutionError):
            SimulatedCampaignExecutionAdapter.execute_campaign(cid)

    def test_12_verification_failure_partial_verification(self):
        """Scenario 11: Verification detects missing dispatch logs and flags failure."""
        cid = "CAMP-VFAIL-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Verification Fail Campaign",
            "business_objective": "Test Verif Fail",
            "reason_for_recommendation": "Testing verif checks",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        v_res = VerificationService.verify_campaign_execution(cid, task_id="TASK-VFAIL")
        self.assertIn(v_res.verification_status, ["FAILED", "REQUIRES_HUMAN"])
        self.assertTrue(len(v_res.failed_checks) > 0)

    def test_13_unauthorized_user_action_blocked(self):
        """Scenario 12: Unauthorized approver triggers HTTP 403 Forbidden."""
        cid = "CAMP-AUTH-P7-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Auth Test Campaign",
            "business_objective": "Test 403",
            "reason_for_recommendation": "Testing authorization rejection",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        body = json.dumps({"approver_id": "ROGUE-ATTACKER", "max_budget_authorized": 5000.0}).encode("utf-8")
        handler = DummyHandler(f"/api/approvals/{cid}/approve", method="POST", body=body)
        self.assertEqual(get_status_code(handler), 403)
        self.assertEqual(get_response_data(handler).get("code"), "UNAUTHORIZED_APPROVER")

    def test_14_category_c_financial_action_strictly_blocked(self):
        """Scenario 13: Category C financial operations (refunds) are strictly blocked."""
        ref_res = registry.execute(
            "issue_refund",
            {"order_id": "ORD-DEMO-999", "amount_inr": 450.0, "reason": "Customer complaint"}
        )
        self.assertEqual(ref_res.status, "FAILED")
        self.assertIn("FINANCIAL_ACTION_BLOCKED", ref_res.error_message)

    def test_15_safe_demo_reset_endpoint(self):
        """Scenario 14: Safe demo reset endpoint restores state cleanly without schema drops."""
        handler = DummyHandler("/api/demo/reset", method="POST", body=b"{}")
        self.assertEqual(get_status_code(handler), 200)
        data = get_response_data(handler)
        self.assertEqual(data["status"], "DEMO_RESET_COMPLETE")
        self.assertEqual(data["campaign_id"], "CAMP-REC-1042")

        # Verify draft is PENDING_APPROVAL
        draft = CampaignService.get_campaign_draft("CAMP-REC-1042")
        self.assertEqual(draft.status, "PENDING_APPROVAL")

    def test_16_sqlite_persistence_across_connections(self):
        """Scenario 15: SQLite database persists records across separate connections."""
        conn1 = sqlite3.connect(DB_PATH)
        c1 = conn1.cursor()
        c1.execute("INSERT OR REPLACE INTO merchants (id, store_name, owner_name, email, phone, city, soundbox_device_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ("MERCH-PERSIST-TEST", "Persistence Test Shop", "Tester", "test@example.com", "9876543210", "Jaipur", "SB-TEST-001"))
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(DB_PATH)
        c2 = conn2.cursor()
        c2.execute("SELECT store_name FROM merchants WHERE id = ?", ("MERCH-PERSIST-TEST",))
        row = c2.fetchone()
        conn2.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Persistence Test Shop")


if __name__ == "__main__":
    unittest.main()
