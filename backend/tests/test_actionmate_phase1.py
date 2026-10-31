"""Paytm AI ActionMate Phase 1 Automated Test Suite.
Validates the merchant foundation, weekly sales analysis, Task #1042 plan generation,
HMAC approval gates, simulated execution, outcome verification, and SPA routing.
"""

import io
import json
import unittest
from backend.app.server import DealPilotRequestHandler, get_sales_weekly_summary, get_actionmate_task_details
from backend.app.database import init_db
from backend.app.fsm import get_workflow, reset_to_initial_state

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

def get_response_body(handler):
    raw = handler.wfile.getvalue()
    if b"\r\n\r\n" in raw:
        return raw.split(b"\r\n\r\n", 1)[1].decode("utf-8")
    elif b"\n\n" in raw:
        return raw.split(b"\n\n", 1)[1].decode("utf-8")
    return raw.decode("utf-8")

class TestActionMatePhase1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        reset_to_initial_state("WF-REC-1042")

    def tearDown(self):
        reset_to_initial_state("WF-REC-1042")

    def test_01_sales_weekly_summary_specification_data(self):
        """Verifies weekly sales data strictly conforms to PPT Slide 4 numbers (Mon-Sun in ₹k)."""
        summary = get_sales_weekly_summary()
        self.assertEqual(summary["status"], "SUCCESS")
        self.assertTrue(summary["is_mock"])
        self.assertEqual(summary["last_week_total_k"], 412)
        self.assertEqual(summary["this_week_total_k"], 300)
        self.assertEqual(summary["overall_drop_pct"], -27.2)
        self.assertEqual(summary["repeat_purchase_drop_pct"], -13.0)
        self.assertEqual(summary["revenue_leakage_inr"], 20900.0)
        self.assertEqual(summary["missing_patrons_count"], 46)
        self.assertEqual(summary["target_cohort_size"], 46)

        # Check daily numbers match presentation
        breakdown = summary["daily_breakdown"]
        self.assertEqual(len(breakdown), 7)
        self.assertEqual(breakdown[0], {"day": "Mon", "last_week": 52, "this_week": 51, "change_pct": -1.9})
        self.assertEqual(breakdown[3], {"day": "Thu", "last_week": 58, "this_week": 40, "change_pct": -31.0})
        self.assertEqual(breakdown[6], {"day": "Sun", "last_week": 66, "this_week": 37, "change_pct": -43.9})

        api_summary = json.loads(get_response_body(DummyHandler("/api/sales/summary")))
        self.assertEqual(api_summary["repeat_purchase_trend"]["current_repeat_rate_pct"], 24.0)
        self.assertEqual(api_summary["repeat_purchase_trend"]["historical_repeat_rate_pct"], 37.0)

    def test_02_task_plan_generation_from_prompt(self):
        """Verifies submitting merchant natural-language request generates Task #1042 with 7-step plan."""
        task = get_actionmate_task_details("WF-REC-1042", "My sales have dropped this week. Help me bring customers back.")
        self.assertEqual(task["task_id"], "WF-REC-1042")
        self.assertEqual(task["merchant"]["id"], "MERCH-001")
        self.assertEqual(task["merchant"]["device_id"], "SB-4G-DEL-9842")

        # 7-Step Plan Verification
        plan = task["plan"]
        self.assertEqual(len(plan), 7)
        self.assertEqual(plan[0]["name"], "Weekly Sales Analysis")
        self.assertEqual(plan[1]["name"], "Repeat-Purchase Trend Analysis")
        self.assertEqual(plan[2]["name"], "Campaign Recommendation")
        self.assertEqual(plan[3]["name"], "Personalised Message Drafting")
        self.assertEqual(plan[4]["name"], "Merchant Approval Gate")
        self.assertEqual(plan[5]["name"], "Simulated Execution")
        self.assertEqual(plan[6]["name"], "Outcome Verification & Audit")

        # Incentive economics verification
        rec = task["recommendation"]
        self.assertEqual(rec["discount_code"], "GROCERY50")
        self.assertEqual(rec["discount_amount_inr"], 50.0)
        self.assertEqual(rec["min_order_inr"], 499.0)
        self.assertEqual(rec["max_liability_cap_inr"], 3600.0)
        self.assertIsNone(rec["projected_roi_multiple"])

    def test_03_spa_route_serving(self):
        """Verifies all application and public routes serve index.html with 200 OK."""
        routes = [
            "/", "/login", "/signup", "/forgot-password",
            "/app/overview", "/app/assistant", "/app/sales",
            "/app/customers", "/app/campaigns", "/app/approvals",
            "/app/activity", "/app/analytics", "/app/settings"
        ]
        for r in routes:
            h = DummyHandler(r, "GET")
            body = get_response_body(h)
            self.assertIn("<!DOCTYPE html>", body, f"Route {r} failed to return HTML")
            self.assertIn("Paytm AI ActionMate", body, f"Route {r} missing brand title")

    def test_04_approval_gate_hmac_enforcement(self):
        """Verifies merchant approval gate generates cryptographic HMAC signature and advances FSM."""
        body = json.dumps({
            "approved_by": "Ramesh Sharma (Merchant Owner)",
            "max_budget_authorized": 3600.0
        }).encode("utf-8")

        h = DummyHandler("/api/actionmate/tasks/WF-REC-1042/approve", "POST", body)
        resp = json.loads(get_response_body(h))
        self.assertEqual(resp["status"], "APPROVED")
        self.assertIn("signature", resp)
        self.assertEqual(len(resp["signature"]), 64)  # 64-char SHA256 hex string

        # Verify workflow state in DB
        wf = get_workflow("WF-REC-1042")
        self.assertEqual(wf["current_state"], "APPROVED")

    def test_05_simulated_execution_and_closed_loop_roi(self):
        """Verifies simulated execution and verified closed-loop ROI accounting."""
        # Execute
        h = DummyHandler("/api/actionmate/tasks/WF-REC-1042/simulate-execution", "POST", b"{}")
        resp = json.loads(get_response_body(h))
        self.assertEqual(resp["status"], "COMPLETED")

        roi = resp["roi"]
        self.assertEqual(roi["redemption_count"], 44)
        self.assertEqual(roi["gross_recovered_sales_inr"], 16940.0)
        self.assertEqual(roi["total_discounts_paid_inr"], 2200.0)
        self.assertEqual(roi["net_recovered_profit_inr"], 14644.0)
        self.assertEqual(roi["roi_multiple"], 6.38)
        self.assertTrue(roi["is_verified"])

if __name__ == "__main__":
    unittest.main()
