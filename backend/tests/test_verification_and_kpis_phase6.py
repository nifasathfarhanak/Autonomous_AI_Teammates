"""Paytm AI ActionMate Phase 6 Verification, Failure Recovery & KPI Analytics Test Suite.
Validates:
1. Multi-point Verification Engine (7 verification invariants).
2. Partial verification detection on anomaly.
3. Failed verification handling.
4. Requires-human escalation when approval is missing.
5. Idempotent retry execution with recipient session refresh.
6. Max retry limits enforcement (Max 2 retries) and automatic escalation.
7. KPI 1: Task Completion Rate calculation.
8. KPI 2: Average Resolution Time calculation.
9. KPI 3: Human Escalation Rate calculation.
10. KPI 4 & 5: Approval Compliance & Cost per Completed Task calculations.
11. KPI 6: Campaign Engagement & Empty Data handling.
12. Executive Task Audit Reporting and Markdown export.
"""

import io
import json
import unittest
from backend.app.database import init_db, get_connection
from backend.app.services.campaign_service import CampaignService
from backend.app.services.governance_service import GovernanceService
from backend.app.services.simulated_execution_adapter import SimulatedCampaignExecutionAdapter
from backend.app.services.verification_service import VerificationService
from backend.app.services.failure_recovery_service import FailureRecoveryService, RecoveryError
from backend.app.services.kpi_service import KPIService
from backend.app.services.reporting_service import TaskReportingService
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

class TestVerificationAndKPIsPhase6(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        """Cleans up test artifacts to guarantee test isolation."""
        conn = get_connection()
        cur = conn.cursor()
        test_cids = [
            "CAMP-P6-VERIF-01",
            "CAMP-P6-PARTIAL-02",
            "CAMP-P6-FAIL-03",
            "CAMP-P6-REQHUM-04",
            "CAMP-P6-RETRY-05",
            "CAMP-P6-MAXRETRY-06",
            "CAMP-P6-ENG-11"
        ]
        test_tids = ["TASK-P6-TEST-01", "TASK-P6-ESC-02", "TASK-P6-RETRY-03"]
        c_placeholders = ",".join(["?"] * len(test_cids))
        t_placeholders = ",".join(["?"] * len(test_tids))

        cur.execute(f"DELETE FROM verifications WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM task_escalations WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM task_escalations WHERE task_id IN ({t_placeholders})", test_tids)
        cur.execute(f"DELETE FROM campaign_recipient_statuses WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM campaign_activity_timeline WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM campaign_drafts WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM approvals WHERE campaign_id IN ({c_placeholders})", test_cids)
        cur.execute(f"DELETE FROM tasks WHERE task_id IN ({t_placeholders})", test_tids)
        conn.commit()
        conn.close()

    def test_01_successful_verification(self):
        """Validates all 7 verification points pass on an authorized and executed campaign."""
        cid = "CAMP-P6-VERIF-01"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Full Verification Campaign",
            "business_objective": "Test 7-Point Verification",
            "reason_for_recommendation": "Testing invariant verification",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        SimulatedCampaignExecutionAdapter.execute_campaign(cid)

        # Run Verification Service
        res = VerificationService.verify_campaign_execution(cid, task_id="TASK-P6-TEST-01")

        self.assertEqual(res.verification_status, "VERIFIED")
        self.assertEqual(len(res.failed_checks), 0)
        self.assertEqual(len(res.verified_checks), 7)
        self.assertIn("check_approval", res.verified_checks)
        self.assertIn("check_adapter_acceptance", res.verified_checks)
        self.assertIn("check_execution_record", res.verified_checks)
        self.assertIn("check_execution_id", res.verified_checks)
        self.assertIn("check_recipient_processing", res.verified_checks)
        self.assertIn("check_statuses_recorded", res.verified_checks)
        self.assertIn("check_workflow_match", res.verified_checks)

        # Verify status in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT verification_status, verification_id FROM campaign_drafts WHERE campaign_id = ?", (cid,))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["verification_status"], "VERIFIED")
        self.assertTrue(row["verification_id"].startswith("VERIF-"))

    def test_02_partial_verification(self):
        """Validates partial verification detection when an audience anomaly occurs."""
        cid = "CAMP-P6-PARTIAL-02"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Partial Verification Campaign",
            "business_objective": "Test Partial Verification",
            "reason_for_recommendation": "Testing partial state detection",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        SimulatedCampaignExecutionAdapter.execute_campaign(cid)

        # Introduce an audience expectation mismatch (simulate 100 expected vs 43 processed)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE campaign_drafts
        SET audience_json = '{"total_evaluated": 110, "eligible_count": 100, "excluded_count": 10}'
        WHERE campaign_id = ?
        """, (cid,))
        conn.commit()
        conn.close()

        res = VerificationService.verify_campaign_execution(cid, task_id="TASK-P6-TEST-01")
        self.assertEqual(res.verification_status, "PARTIALLY_VERIFIED")
        self.assertIn("check_recipient_processing", res.failed_checks)
        self.assertIn("check_workflow_match", res.failed_checks)
        self.assertIn("check_approval", res.verified_checks)

    def test_03_failed_verification(self):
        """Validates failed verification on an unexecuted draft with no recipient processing."""
        cid = "CAMP-P6-FAIL-03"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Failed Verification Campaign",
            "business_objective": "Test Failure Handling",
            "reason_for_recommendation": "Testing unexecuted draft failure",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        # Do NOT execute

        res = VerificationService.verify_campaign_execution(cid, task_id="TASK-P6-TEST-01")
        self.assertEqual(res.verification_status, "FAILED")
        self.assertIn("check_adapter_acceptance", res.failed_checks)
        self.assertIn("check_execution_id", res.failed_checks)
        self.assertIn("check_recipient_processing", res.failed_checks)

    def test_04_verification_requires_human_on_unapproved_campaign(self):
        """Validates that missing merchant approval flags verification as REQUIRES_HUMAN."""
        cid = "CAMP-P6-REQHUM-04"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Missing Approval Campaign",
            "business_objective": "Test Approval Requirement",
            "reason_for_recommendation": "Testing unapproved escalation",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        # Note: Zero approval granted

        res = VerificationService.verify_campaign_execution(cid, task_id="TASK-P6-TEST-01")
        self.assertEqual(res.verification_status, "REQUIRES_HUMAN")
        self.assertIn("check_approval", res.failed_checks)

    def test_05_retry_handling_idempotent(self):
        """Validates controlled idempotent campaign retry with session and recipient cleanup."""
        cid = "CAMP-P6-RETRY-05"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Retry Handling Campaign",
            "business_objective": "Test Idempotent Retry",
            "reason_for_recommendation": "Testing retry mechanism",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")

        # Simulate a failed draft state
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE campaign_drafts SET status = 'FAILED' WHERE campaign_id = ?", (cid,))
        conn.commit()
        conn.close()

        # Execute safe retry
        retry_res = FailureRecoveryService.retry_campaign_execution(cid, task_id="TASK-P6-RETRY-03")

        self.assertEqual(retry_res["retry_attempt"], 1)
        self.assertEqual(retry_res["max_retries"], 2)
        self.assertEqual(retry_res["execution_status"], "COMPLETED")
        self.assertEqual(retry_res["verification_status"], "VERIFIED")
        self.assertTrue(retry_res["verified"])

    def test_06_retry_limit_exceeded_auto_escalation(self):
        """Validates that exceeding max retries (Max 2) blocks blind retries and triggers human escalation."""
        cid = "CAMP-P6-MAXRETRY-06"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Max Retry Campaign",
            "business_objective": "Test Retry Limit Enforcement",
            "reason_for_recommendation": "Testing auto-escalation",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": False
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")

        # Set retry_count to 2 in DB (reaching limit)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE campaign_drafts SET status = 'FAILED', retry_count = 2 WHERE campaign_id = ?", (cid,))
        conn.commit()
        conn.close()

        # Attempt 3rd retry: must fail with RecoveryError
        with self.assertRaises(RecoveryError) as ctx:
            FailureRecoveryService.retry_campaign_execution(cid, task_id="TASK-P6-RETRY-03")
        self.assertIn("RETRY_BLOCKED", str(ctx.exception))
        self.assertIn("maximum retry limit", str(ctx.exception).lower())

        # Verify auto-escalation record was written
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM task_escalations WHERE task_id = 'TASK-P6-RETRY-03'",)
        esc_row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(esc_row)
        self.assertIn("Auto-escalation", esc_row["escalation_reason"])
        self.assertEqual(esc_row["status"], "PENDING_HUMAN")

    def test_07_task_completion_rate_calculation(self):
        """Validates KPI 1: Task Completion Rate calculation formula."""
        kpis = KPIService.calculate_kpis("MERCH-001")

        self.assertTrue(kpis["has_data"])
        comp_rate = kpis["kpis"]["task_completion_rate"]
        self.assertGreaterEqual(comp_rate, 0.0)
        self.assertLessEqual(comp_rate, 100.0)

        # Verify formula: completed / total_eligible * 100
        counts = kpis["counts"]
        if counts["total_eligible_tasks"] > 0:
            expected = round((counts["completed_tasks"] / counts["total_eligible_tasks"]) * 100.0, 1)
            self.assertEqual(comp_rate, expected)

    def test_08_average_resolution_time_calculation(self):
        """Validates KPI 2: Average Resolution Time calculation for completed tasks."""
        kpis = KPIService.calculate_kpis("MERCH-001")
        avg_res = kpis["kpis"]["average_resolution_time_min"]
        if avg_res is None:
            self.assertEqual(kpis["kpis"]["average_resolution_display"], "Not measured")
        else:
            self.assertGreater(avg_res, 0.0)
            self.assertIn("min", kpis["kpis"]["average_resolution_display"])

    def test_09_human_escalation_rate_calculation(self):
        """Validates KPI 3: Human Escalation Rate calculation."""
        # Escalate a test task
        FailureRecoveryService.escalate_to_human(
            task_id="TASK-P6-ESC-02",
            campaign_id="CAMP-P6-VERIF-01",
            reason="High-value quotation anomaly."
        )

        kpis = KPIService.calculate_kpis("MERCH-001")
        esc_rate = kpis["kpis"]["human_escalation_rate"]
        self.assertGreater(esc_rate, 0.0)
        self.assertIn("%", kpis["kpis"]["human_escalation_display"])
        self.assertGreaterEqual(kpis["counts"]["escalated_tasks"], 1)

    def test_10_approval_compliance_and_cost_calculation(self):
        """Validates KPI 4 (Approval Compliance) and KPI 5 (Cost per Completed Task)."""
        kpis = KPIService.calculate_kpis("MERCH-001")

        # KPI 4
        compliance = kpis["kpis"]["approval_compliance"]
        if compliance is not None:
            self.assertEqual(compliance, 100.0)
            self.assertEqual(kpis["kpis"]["approval_compliance_display"], "100.0%")
        else:
            self.assertEqual(kpis["kpis"]["approval_compliance_display"], "N/A")

        # KPI 5
        cost = kpis["kpis"]["cost_per_completed_task_inr"]
        self.assertGreater(cost, 0.0)
        self.assertIn("₹", kpis["kpis"]["cost_per_completed_task_display"])
        self.assertEqual(kpis["cost_metric_definition"]["illustrative_unit_cost_inr"], 3.10)

    def test_11_campaign_engagement_and_empty_data_handling(self):
        """Validates KPI 6 (Campaign Engagement) and empty data filter handling."""
        cid = "CAMP-P6-ENG-11"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Engagement Test Campaign",
            "business_objective": "Test Engagement Metrics",
            "reason_for_recommendation": "Testing engagement rate",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True
        })
        GovernanceService.approve_campaign(cid, approver_id="USER-001")
        SimulatedCampaignExecutionAdapter.execute_campaign(cid)

        kpis = KPIService.calculate_kpis("MERCH-001")
        eng_rate = kpis["kpis"]["campaign_engagement_rate"]
        expected_engagement = round(
            (kpis["counts"]["total_engaged_recipients"] / kpis["counts"]["total_delivered_recipients"]) * 100.0,
            1
        ) if kpis["counts"]["total_delivered_recipients"] else 0.0
        self.assertEqual(eng_rate, expected_engagement)
        self.assertIn("%", kpis["kpis"]["campaign_engagement_display"])
        self.assertIn("denominator_description", kpis["engagement_metric_definition"])

        # Empty data handling: query non-existent merchant
        empty_res = KPIService.calculate_kpis("NONEXISTENT_MERCH_999")
        self.assertFalse(empty_res["has_data"])
        self.assertEqual(empty_res["kpis"]["task_completion_rate"], 0.0)
        self.assertEqual(empty_res["kpis"]["approval_compliance_display"], "N/A")
        self.assertEqual(empty_res["kpis"]["cost_per_completed_task_inr"], 0.0)

    def test_12_task_reporting_and_markdown_export(self):
        """Validates comprehensive task audit report generation and Markdown export."""
        report = TaskReportingService.generate_task_report("WF-REC-1042")
        self.assertEqual(report.task_id, "WF-REC-1042")
        self.assertEqual(report.merchant_id, "MERCH-001")
        self.assertIn("sales have dropped", report.original_request)
        self.assertIn("weekly_sales_trend", report.sales_findings)
        self.assertIn("detected_intent", report.ai_interpretation)
        self.assertIn("campaign_name", report.recommended_campaign)
        self.assertIn("status", report.approval_decision)
        self.assertIn("status", report.execution_result)
        self.assertIn("status", report.verification_result)
        self.assertGreater(len(report.audit_history), 0)

        # Markdown Export
        md = TaskReportingService.export_report_markdown("WF-REC-1042")
        self.assertIn("# Paytm AI ActionMate — Executive Task Audit Report", md)
        self.assertIn("Original Merchant Request & Business Context", md)
        self.assertIn("Diagnostic Sales Intelligence Findings", md)
        self.assertIn("Execution & Verification Results", md)
        self.assertIn("Cryptographic Audit Ledger Trail", md)

        # HTTP REST Endpoint
        handler = DummyHandler("/api/reports/task/WF-REC-1042", method="GET")
        self.assertEqual(get_status_code(handler), 200)
        resp_data = get_response_data(handler)
        self.assertEqual(resp_data["task_id"], "WF-REC-1042")

if __name__ == "__main__":
    unittest.main()
