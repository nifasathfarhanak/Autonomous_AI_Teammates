"""Comprehensive Hackathon Demo Readiness & End-to-End Journey Verification Test.
Simulates and validates the entire 14-step merchant journey:
From Sales Drop Detection to Decision Twin Simulation, Guardrail Governance,
Cryptographic Approval, Omnichannel Execution, 7-Point Verification,
Treatment vs Holdout Causal Lift, Audit Ledger, and One-Click Reset.
"""

import unittest
import json
from io import BytesIO
from backend.app.database import init_db, get_connection
from backend.app.server import DealPilotRequestHandler


class DummyHandler(DealPilotRequestHandler):
    """In-memory request handler for testing REST endpoints without active socket binding."""
    def __init__(self, method: str, path: str, body: dict = None):
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.close_connection = False
        self.headers = {"Content-Type": "application/json"}
        
        body_bytes = json.dumps(body).encode('utf-8') if body else b""
        self.headers["Content-Length"] = str(len(body_bytes))
        self.rfile = BytesIO(body_bytes)
        self.wfile = BytesIO()
        self.status_code = None
        self.response_headers = {}

    def _set_headers(self, code=200, content_type="application/json"):
        self.status_code = code
        self.response_headers["Content-Type"] = content_type

    def get_response_json(self):
        output = self.wfile.getvalue()
        if not output:
            return {}
        try:
            return json.loads(output.decode('utf-8'))
        except Exception:
            return {"raw": output.decode('utf-8')}

    def get_response_text(self):
        return self.wfile.getvalue().decode('utf-8')


class TestHackathonDemoReadiness(unittest.TestCase):
    """Verifies the complete end-to-end merchant journey and demo readiness."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_demo_reset_and_initial_clean_state(self):
        """Step 0: One-click demo reset restores pristine baseline state."""
        h = DummyHandler("POST", "/api/demo/reset", {})
        h.do_POST()
        self.assertEqual(h.status_code, 200)
        res = h.get_response_json()
        self.assertEqual(res["status"], "DEMO_RESET_COMPLETE")
        self.assertEqual(res["task_id"], "WF-REC-1042")
        self.assertEqual(res["campaign_id"], "CAMP-REC-1042")

    def test_02_dashboard_sales_and_drop_detection(self):
        """Step 1-4: Merchant views sales, AI detects -27.2% drop and repeat purchase collapse."""
        # 1. Sales Summary
        h_sales = DummyHandler("GET", "/api/sales/summary")
        h_sales.do_GET()
        self.assertEqual(h_sales.status_code, 200)
        sales = h_sales.get_response_json()
        self.assertEqual(sales["last_week_total_k"], 412.0)
        self.assertEqual(sales["this_week_total_k"], 300.0)
        self.assertEqual(sales["overall_drop_pct"], -27.2)

        # 2. Merchant Profile (Soundbox Telemetry)
        h_prof = DummyHandler("GET", "/api/merchant/profile")
        h_prof.do_GET()
        self.assertEqual(h_prof.status_code, 200)
        prof = h_prof.get_response_json()
        self.assertEqual(prof["soundbox_device_id"], "SB-4G-DEL-9842")
        self.assertEqual(prof["soundbox_status"], "ONLINE")

        # 3. Sales Drop Detection Evidence
        h_drop = DummyHandler("GET", "/api/sales/drop-detection")
        h_drop.do_GET()
        self.assertEqual(h_drop.status_code, 200)
        drop = h_drop.get_response_json()
        self.assertTrue(drop["is_drop_detected"])
        self.assertEqual(drop["drop_severity"], "HIGH")
        self.assertGreater(len(drop["supporting_evidence"]), 0)

    def test_03_customer_profit_inventory_intelligence(self):
        """Step 5: AI analyzes customer value (RFM), product gross margins, and inventory velocities."""
        # 1. Customer RFM
        h_rfm = DummyHandler("GET", "/api/customers/rfm?merchant_id=MERCH-001")
        h_rfm.do_GET()
        self.assertEqual(h_rfm.status_code, 200)
        custs = h_rfm.get_response_json()
        self.assertGreaterEqual(len(custs), 5)
        self.assertTrue(any(c["segment"] == "DECLINING_FREQUENCY" for c in custs))

        # 2. Profit Catalog
        h_profit = DummyHandler("GET", "/api/profit/catalog?merchant_id=MERCH-001")
        h_profit.do_GET()
        self.assertEqual(h_profit.status_code, 200)
        catalog = h_profit.get_response_json()
        self.assertGreaterEqual(len(catalog), 8)
        self.assertTrue(any("HIGH_MARGIN" in p["classification"] or "BEST_SELLER" in p["classification"] for p in catalog))

        # 3. Inventory Velocity & Stockout Risk
        h_inv = DummyHandler("GET", "/api/inventory/status?merchant_id=MERCH-001")
        h_inv.do_GET()
        self.assertEqual(h_inv.status_code, 200)
        inv = h_inv.get_response_json()
        self.assertGreaterEqual(len(inv), 8)
        self.assertTrue(any(i["days_on_hand"] > 0 for i in inv))

    def test_04_proactive_business_opportunities(self):
        """Step 6: AI radar surfaces ranked business opportunities across Profit, Inventory, and Cash-Flow."""
        h_opps = DummyHandler("GET", "/api/opportunities/ranked?merchant_id=MERCH-001")
        h_opps.do_GET()
        self.assertEqual(h_opps.status_code, 200)
        opps = h_opps.get_response_json()
        self.assertGreaterEqual(len(opps), 4)
        # Verify sorted by priority score
        self.assertGreaterEqual(opps[0]["priority_rank_score"], opps[-1]["priority_rank_score"])

    def test_05_decision_twin_multi_strategy_simulation(self):
        """Step 7 & 8: Merchant simulates 4 competing strategies in the Decision Twin."""
        h_sim = DummyHandler("POST", "/api/decision-twin/simulate", {
            "merchant_id": "MERCH-001",
            "budget_limit_inr": 3600.0,
            "discount_cap_pct": 10.0,
            "min_margin_floor_pct": 25.0,
            "audience_size": 43
        })
        h_sim.do_POST()
        self.assertEqual(h_sim.status_code, 200)
        sim = h_sim.get_response_json()
        self.assertIn("strategies_simulated", sim)
        self.assertEqual(len(sim["strategies_simulated"]), 4)
        self.assertIn("recommended_strategy", sim)
        self.assertIn("decision_twin_verdict", sim)

    def test_06_business_guardrails_validation(self):
        """Step 9: Merchant business guardrails validate proposed campaign parameters."""
        # 1. Fetch current rules
        h_gr = DummyHandler("GET", "/api/guardrails?merchant_id=MERCH-001")
        h_gr.do_GET()
        self.assertEqual(h_gr.status_code, 200)
        rules = h_gr.get_response_json()
        self.assertGreaterEqual(len(rules), 6)

        # 2. Evaluate proposed RET50 campaign
        h_eval = DummyHandler("POST", "/api/guardrails/evaluate", {
            "merchant_id": "MERCH-001",
            "discount_pct": 2.4, # RET50 on ~2100 basket = 2.4%
            "total_budget_inr": 133.30, # 43 msgs * 3.10
            "estimated_margin_pct": 32.9
        })
        h_eval.do_POST()
        self.assertEqual(h_eval.status_code, 200)
        evaluation = h_eval.get_response_json()
        self.assertTrue(evaluation["passed"])
        self.assertEqual(len(evaluation["violations"]), 0)

    def test_07_merchant_campaign_approval_and_hmac_signature(self):
        """Step 10: Merchant reviews campaign and signs off with cryptographic HMAC."""
        # 1. Approve campaign via Governance Engine
        h_appr = DummyHandler("POST", "/api/approvals/CAMP-REC-1042/approve", {
            "merchant_id": "MERCH-001",
            "approver_id": "USER-001",
            "max_budget_authorized": 3600.0,
            "comments": "Approved by merchant Ramesh Sharma for weekend recovery"
        })
        h_appr.do_POST()
        self.assertEqual(h_appr.status_code, 200)
        appr_res = h_appr.get_response_json()
        self.assertEqual(appr_res["approval_status"], "VALID")
        self.assertEqual(appr_res["decision"], "APPROVED")
        self.assertIn("auth_signature", appr_res)

        # 2. Advance Orchestrator Task FSM
        h_task_appr = DummyHandler("POST", "/api/actionmate/tasks/WF-REC-1042/approve", {
            "approved_by": "Ramesh Sharma (Merchant Owner)",
            "max_budget": 3600.0
        })
        h_task_appr.do_POST()
        self.assertEqual(h_task_appr.status_code, 200)

    def test_08_simulated_execution_and_receipt_generation(self):
        """Step 11 & 12: System executes simulated omnichannel action and logs receipts."""
        h_exec = DummyHandler("POST", "/api/campaigns/drafts/CAMP-REC-1042/execute-simulated", {
            "caller": "Ramesh Sharma (Merchant Owner)"
        })
        h_exec.do_POST()
        self.assertEqual(h_exec.status_code, 200)
        exec_res = h_exec.get_response_json()
        self.assertIn("execution_id", exec_res)
        self.assertGreater(exec_res["total_attempted"], 0)
        self.assertGreater(exec_res["delivered_count"], 0)
        self.assertEqual(exec_res["status"], "COMPLETED")

    def test_09_verification_engine_audit(self):
        """Step 13: 7-point verification engine audits execution before reporting complete."""
        h_verif = DummyHandler("POST", "/api/verification/verify/CAMP-REC-1042", {
            "task_id": "WF-REC-1042"
        })
        h_verif.do_POST()
        self.assertEqual(h_verif.status_code, 200)
        verif_res = h_verif.get_response_json()
        self.assertEqual(verif_res["verification_status"], "VERIFIED")
        self.assertGreaterEqual(len(verif_res["verified_checks"]), 7)

    def test_10_reality_check_treatment_vs_holdout_lift(self):
        """Step 14: Reality check calculates true incremental causal lift over holdout baseline."""
        h_exp = DummyHandler("GET", "/api/outcomes/incremental?campaign_id=CAMP-REC-1042&merchant_id=MERCH-001")
        h_exp.do_GET()
        self.assertEqual(h_exp.status_code, 200)
        exp = h_exp.get_response_json()
        self.assertIn("treatment_group", exp)
        self.assertIn("holdout_group", exp)
        self.assertIn("incremental_impact", exp)
        self.assertEqual(exp["provenance_badge"], "SIMULATED_DEMO")
        self.assertGreater(exp["incremental_impact"]["incremental_gross_profit_inr"], 0)

    def test_11_audit_trail_and_executive_report_export(self):
        """Step 15 & 16: Cryptographic audit trail and downloadable executive task report."""
        # 1. Audit Trail
        h_audit = DummyHandler("GET", "/api/audit/trail")
        h_audit.do_GET()
        self.assertEqual(h_audit.status_code, 200)
        trail = h_audit.get_response_json()
        self.assertIn("ledger", trail)
        self.assertTrue(trail["chain_integrity_valid"])

        # 2. Markdown Report Export
        h_rep = DummyHandler("GET", "/api/reports/task/WF-REC-1042/export")
        h_rep.do_GET()
        self.assertEqual(h_rep.status_code, 200)
        md = h_rep.get_response_text()
        self.assertIn("Paytm AI ActionMate", md)
        self.assertIn("Executive Task Audit Report", md)
        self.assertIn("WF-REC-1042", md)

    def test_12_repeat_demo_reset_cleanliness(self):
        """Step 17: Post-demo reset successfully cleans up for consecutive presentations."""
        h_reset = DummyHandler("POST", "/api/demo/reset", {})
        h_reset.do_POST()
        self.assertEqual(h_reset.status_code, 200)

        # Verify task is back in READY_FOR_APPROVAL
        h_task = DummyHandler("GET", "/api/actionmate/tasks/WF-REC-1042")
        h_task.do_GET()
        self.assertEqual(h_task.status_code, 200)
        task = h_task.get_response_json()
        self.assertEqual(task["current_state"], "READY_FOR_APPROVAL")


if __name__ == "__main__":
    unittest.main()
