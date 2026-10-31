"""Paytm AI ActionMate Phase 4 Automated Test Suite.
Validates campaign recommendation, deterministic audience targeting and exclusion rules,
personalized multilingual message drafting (with and without offers),
the 8 campaign tools in the registry, simulated multi-channel execution adapter,
idempotency / duplicate execution prevention, and Phase 4 HTTP endpoints.
"""

import json
import unittest
from backend.app.database import init_db, get_connection
from backend.app.services.campaign_service import CampaignService
from backend.app.services.governance_service import GovernanceService
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
        import io
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

class TestCampaignExecutionPhase4(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        """Cleans up test artifacts to guarantee test isolation."""
        conn = get_connection()
        cur = conn.cursor()
        test_ids = ["CAMP-TEST-TOOL-01", "CAMP-EXEC-TEST-02", "CAMP-EXEC-IDEMP-03", "CAMP-EXEC-EMPTY-04"]
        placeholders = ",".join(["?"] * len(test_ids))
        cur.execute(f"DELETE FROM campaign_recipient_statuses WHERE campaign_id IN ({placeholders})", test_ids)
        cur.execute(f"DELETE FROM campaign_activity_timeline WHERE campaign_id IN ({placeholders})", test_ids)
        cur.execute(f"DELETE FROM campaign_drafts WHERE campaign_id IN ({placeholders})", test_ids)
        conn.commit()
        conn.close()

    def test_01_campaign_recommendation_structure_and_rationale(self):
        """Validates structured campaign recommendation based on sales drop without fabricated revenue."""
        rec = CampaignService.recommend_campaign_for_sales_drop("MERCH-001")

        self.assertIsNotNone(rec)
        self.assertIn("Recovery Campaign", rec.campaign_name)
        self.assertIn("24.0%", rec.reason_for_recommendation)
        self.assertIn("repeat", rec.reason_for_recommendation.lower())
        self.assertTrue(rec.target_customer_segment.startswith("DECLINING_FREQUENCY"))
        self.assertIn("7 days", rec.suggested_campaign_duration)
        self.assertIn("Soundbox", rec.recommended_communication_channel)
        self.assertIn("SMS", rec.recommended_communication_channel)
        self.assertTrue(rec.is_demo)

        # Confirm offer structure
        self.assertEqual(rec.offer_details["discount_code"], "GROCERY50")
        self.assertEqual(rec.offer_details["discount_amount_inr"], 50.0)
        self.assertEqual(rec.offer_details["min_order_inr"], 499.0)

        # Confirm no hallucinated revenue guarantees
        self.assertNotIn("guaranteed revenue", rec.expected_operational_outcome.lower())
        self.assertNotIn("100% conversion", rec.expected_operational_outcome.lower())
        self.assertTrue(len(rec.risks_and_assumptions) >= 2)

    def test_02_customer_targeting_and_eligibility(self):
        """Evaluates customer cohort targeting and counts matching database records."""
        aud = CampaignService.evaluate_campaign_audience("MERCH-001", "ALL")

        self.assertEqual(aud.targeting_criteria["merchant_id"], "MERCH-001")
        self.assertEqual(aud.targeting_criteria["segment_key"], "ALL")
        self.assertEqual(aud.total_evaluated, 100)
        self.assertEqual(aud.eligible_count + aud.excluded_count, aud.total_evaluated)
        self.assertEqual(aud.excluded_count, 3)
        self.assertEqual(aud.eligible_count, 97)
        self.assertEqual(len(aud.eligible_customers), 97)
        self.assertEqual(len(aud.excluded_customers), 3)

    def test_03_exclusion_rules_enforcement(self):
        """Verifies deterministic exclusions: unsubscribed, invalid email, and invalid phone."""
        aud = CampaignService.evaluate_campaign_audience("MERCH-001", "ALL")

        # Look up seeded exclusion accounts
        excl_dict = {c["customer_id"]: c["reason"] for c in aud.excluded_customers}

        self.assertIn("CUST-1045", excl_dict)
        self.assertEqual(excl_dict["CUST-1045"], "OPTED_OUT_UNSUBSCRIBED")

        self.assertIn("CUST-1046", excl_dict)
        self.assertEqual(excl_dict["CUST-1046"], "INVALID_EMAIL_ADDRESS")

        self.assertIn("CUST-1047", excl_dict)
        self.assertEqual(excl_dict["CUST-1047"], "INVALID_PHONE_NUMBER")

        # Verify summary counts
        self.assertEqual(aud.exclusion_reasons["OPTED_OUT_UNSUBSCRIBED"], 1)
        self.assertEqual(aud.exclusion_reasons["INVALID_EMAIL_ADDRESS"], 1)
        self.assertEqual(aud.exclusion_reasons["INVALID_PHONE_NUMBER"], 1)

    def test_04_personalized_message_rendering_with_offer(self):
        """Verifies message personalization when an incentive offer is configured."""
        customer = {
            "customer_id": "CUST-1001",
            "customer_name": "Vikram Patel",
            "interested_product": "Premium Basmati Rice"
        }
        merchant_name = "Sharma Commercial & Industrial Supplies"
        offer = {
            "discount_code": "RET50",
            "discount_amount_inr": 50.0,
            "min_order_inr": 249.0
        }

        msg = CampaignService.render_personalized_message(customer, merchant_name, offer)

        self.assertEqual(msg.customer_name, "Vikram Patel")
        self.assertEqual(msg.merchant_name, merchant_name)
        self.assertTrue(msg.offer_configured)
        self.assertIn("Vikram Patel", msg.body_en)
        self.assertIn("₹50", msg.body_en)
        self.assertIn("RET50", msg.body_en)
        self.assertIn("₹249", msg.body_en)
        self.assertIn("Soundbox", msg.body_en)

        # Indic Hindi and Voice script
        self.assertIn("Vikram Patel", msg.body_hi)
        self.assertIn("RET50", msg.body_hi)
        self.assertIn("RET50", msg.soundbox_voice_prompt)

    def test_05_personalized_message_rendering_without_offer(self):
        """Verifies message personalization without offering discounts when unconfigured."""
        customer = {
            "customer_id": "CUST-1002",
            "customer_name": "Pooja Sharma",
            "interested_product": "Organic Spices"
        }
        merchant_name = "Sharma Commercial & Industrial Supplies"

        msg = CampaignService.render_personalized_message(customer, merchant_name, offer_details=None)

        self.assertEqual(msg.customer_name, "Pooja Sharma")
        self.assertFalse(msg.offer_configured)
        self.assertIn("Pooja Sharma", msg.body_en)
        self.assertIn("Sharma Commercial & Industrial Supplies", msg.body_en)
        # Ensure NO discount or coupon was promised
        self.assertNotIn("₹50", msg.body_en)
        self.assertNotIn("RET50", msg.body_en)
        self.assertNotIn("discount", msg.body_en.lower())
        self.assertNotIn("OFF", msg.body_en)

    def test_06_campaign_tools_via_registry(self):
        """Executes all 8 Phase 4 Campaign tools through the controlled ToolRegistry."""
        tools_to_test = [
            ("calculate_campaign_audience", {"merchant_id": "MERCH-001", "segment_key": "DECLINING_FREQUENCY"}),
            ("analyse_customer_segment", {"merchant_id": "MERCH-001", "segment_key": "DECLINING_FREQUENCY"}),
            ("create_campaign_draft", {
                "campaign_id": "CAMP-TEST-TOOL-01",
                "merchant_id": "MERCH-001",
                "campaign_name": "Registry Tool Test Campaign",
                "business_objective": "Test all tools in registry",
                "reason_for_recommendation": "Phase 4 verification",
                "target_customer_segment": "DECLINING_FREQUENCY",
                "offer_configured": True,
                "offer_details": {"discount_code": "RET50", "discount_amount_inr": 50.0, "min_order_inr": 249.0}
            }),
            ("generate_campaign_message", {
                "customer_name": "Ananya Roy",
                "merchant_name": "Sharma Commercial & Industrial Supplies",
                "offer_details": {"discount_code": "RET50", "discount_amount_inr": 50.0, "min_order_inr": 249.0}
            }),
            ("preview_campaign", {"campaign_id": "CAMP-TEST-TOOL-01"}),
            ("validate_campaign_recipients", {"campaign_id": "CAMP-TEST-TOOL-01"}),
            ("submit_campaign_for_approval", {"campaign_id": "CAMP-TEST-TOOL-01"}),
            ("execute_demo_campaign", {"campaign_id": "CAMP-TEST-TOOL-01"})
        ]

        all_perms = [
            "READ_CUSTOMERS", "CREATE_CAMPAIGN", "DRAFT_COMMUNICATION",
            "READ_CAMPAIGNS", "SUBMIT_APPROVAL", "SIMULATE_EXECUTION"
        ]
        # Execute first 7 tools up to approval submission
        for tool_name, args in tools_to_test[:-1]:
            res = registry.execute(tool_name, args, caller_permissions=all_perms)
            self.assertEqual(res.status, "SUCCESS", f"Tool '{tool_name}' failed: {res.error_message}")
            self.assertIsNotNone(res.data, f"Tool '{tool_name}' returned empty data.")
            self.assertTrue(res.verified, f"Verification failed for {tool_name}")

        # Merchant approves the submitted campaign (Human-in-the-Loop Governance)
        GovernanceService.approve_campaign("CAMP-TEST-TOOL-01")

        # Execute the approved demo campaign
        res_exec = registry.execute("execute_demo_campaign", {"campaign_id": "CAMP-TEST-TOOL-01"}, caller_permissions=all_perms)
        self.assertEqual(res_exec.status, "SUCCESS", f"Tool 'execute_demo_campaign' failed: {res_exec.error_message}")
        self.assertIsNotNone(res_exec.data)
        self.assertTrue(res_exec.verified)

    def test_07_simulated_execution_and_recipient_statuses(self):
        """Verifies simulated multi-channel execution, recipient logging, and DND suppression."""
        cid = "CAMP-EXEC-TEST-02"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Full Execution Test",
            "business_objective": "Verify multi-channel dispatch simulation",
            "reason_for_recommendation": "Verify execution adapter",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True,
            "offer_details": {"discount_code": "RET50", "discount_amount_inr": 50.0, "min_order_inr": 249.0}
        })

        # Merchant approves the campaign before execution
        GovernanceService.approve_campaign(cid)

        result = SimulatedCampaignExecutionAdapter.execute_campaign(cid, caller="Integration Test Suite")

        self.assertEqual(result.campaign_id, cid)
        self.assertTrue(result.execution_id.startswith("EXEC-"))
        self.assertEqual(result.status, "COMPLETED")
        self.assertTrue(result.is_demo)
        self.assertGreater(result.total_attempted, 0)
        self.assertGreater(result.delivered_count, 0)
        self.assertGreater(result.dnd_suppressed_count, 0)

        # Verify recipients table in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM campaign_recipient_statuses WHERE campaign_id = ?", (cid,))
        cnt = cur.fetchone()["cnt"]
        self.assertGreaterEqual(cnt, result.total_attempted)

        # Verify DND suppression occurred
        cur.execute("SELECT COUNT(*) as dnd_cnt FROM campaign_recipient_statuses WHERE campaign_id = ? AND simulated_status = 'DND_SUPPRESSED'", (cid,))
        dnd_cnt = cur.fetchone()["dnd_cnt"]
        self.assertEqual(dnd_cnt, result.dnd_suppressed_count)

        conn.close()

    def test_08_duplicate_execution_prevention_idempotency(self):
        """Ensures that executing an already completed campaign raises DuplicateExecutionError."""
        cid = "CAMP-EXEC-IDEMP-03"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Idempotency Test Campaign",
            "business_objective": "Test duplicate prevention",
            "reason_for_recommendation": "Phase 4 safety check",
            "target_customer_segment": "DECLINING_FREQUENCY",
            "offer_configured": True,
            "offer_details": {"discount_code": "RET50", "discount_amount_inr": 50.0, "min_order_inr": 249.0}
        })

        # Merchant approves the campaign before execution
        GovernanceService.approve_campaign(cid)

        # First run succeeds
        res1 = SimulatedCampaignExecutionAdapter.execute_campaign(cid, idempotency_key="KEY-IDEMP-01")
        self.assertEqual(res1.status, "COMPLETED")

        # Second run with same or different key must raise DuplicateExecutionError
        with self.assertRaises(DuplicateExecutionError):
            SimulatedCampaignExecutionAdapter.execute_campaign(cid, idempotency_key="KEY-IDEMP-02")

        # Test HTTP 409 response via DummyHandler
        h = DummyHandler(f"/api/campaigns/drafts/{cid}/execute-simulated", method="POST", body=b"{}")
        status = get_status_code(h)
        self.assertEqual(status, 409)
        resp = get_response_data(h)
        self.assertEqual(resp.get("code"), "DUPLICATE_EXECUTION")

    def test_09_execution_failure_on_empty_audience(self):
        """Ensures that executing a campaign with an empty audience fails safely."""
        cid = "CAMP-EXEC-EMPTY-04"
        CampaignService.create_campaign_draft({
            "campaign_id": cid,
            "merchant_id": "MERCH-001",
            "campaign_name": "Empty Audience Campaign",
            "business_objective": "Test empty audience failure",
            "reason_for_recommendation": "Phase 4 error handling",
            "target_customer_segment": "EMPTY_AUDIENCE",
            "offer_configured": False
        })

        # Merchant approves the campaign before execution
        GovernanceService.approve_campaign(cid)

        with self.assertRaises(ExecutionAdapterError) as ctx:
            SimulatedCampaignExecutionAdapter.execute_campaign(cid)
        self.assertIn("0 eligible customers", str(ctx.exception))

    def test_10_campaign_endpoints_via_dummy_handler(self):
        """Verifies HTTP 200 responses across all Phase 4 campaign REST endpoints."""
        # 1. Recommendation
        h1 = DummyHandler("/api/campaigns/recommendation", method="GET")
        self.assertEqual(get_status_code(h1), 200)
        data1 = get_response_data(h1)
        self.assertIn("campaign_name", data1)

        # 2. Drafts list
        h2 = DummyHandler("/api/campaigns/drafts", method="GET")
        self.assertEqual(get_status_code(h2), 200)
        data2 = get_response_data(h2)
        self.assertIsInstance(data2, list)

        # 3. Target audience POST
        h3 = DummyHandler("/api/campaigns/target-audience", method="POST", body=json.dumps({
            "merchant_id": "MERCH-001",
            "segment_key": "DECLINING_FREQUENCY"
        }).encode("utf-8"))
        self.assertEqual(get_status_code(h3), 200)
        data3 = get_response_data(h3)
        self.assertIn("eligible_count", data3)
        self.assertIn("excluded_count", data3)

        # 4. Preview message POST
        h4 = DummyHandler("/api/campaigns/preview-message", method="POST", body=json.dumps({
            "customer": {"customer_name": "Sanjay Verma", "interested_product": "Commercial fans"},
            "merchant_name": "Sharma Commercial & Industrial Supplies",
            "offer_details": {"discount_code": "RET50", "discount_amount_inr": 50.0, "min_order_inr": 249.0}
        }).encode("utf-8"))
        self.assertEqual(get_status_code(h4), 200)
        data4 = get_response_data(h4)
        self.assertIn("body_en", data4)
        self.assertIn("soundbox_voice_prompt", data4)

        # 5. Submit for approval POST
        cid = data2[0]["campaign_id"] if data2 else "CAMP-REC-1042"
        h5 = DummyHandler(f"/api/campaigns/drafts/{cid}/submit-approval", method="POST", body=b"{}")
        self.assertEqual(get_status_code(h5), 200)

        # 6. Timeline GET
        h6 = DummyHandler(f"/api/campaigns/drafts/{cid}/timeline", method="GET")
        self.assertEqual(get_status_code(h6), 200)
        data6 = get_response_data(h6)
        self.assertIsInstance(data6, list)

if __name__ == "__main__":
    unittest.main()
