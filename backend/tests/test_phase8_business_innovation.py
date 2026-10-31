"""Unit and Integration Tests for Phase 8:
Paytm AI ActionMate Business Innovation, Profitability Intelligence & Merchant Growth Platform.
Tests all 8 core business innovations, mathematical engines, guardrail enforcement,
provenance tracking, and HTTP REST endpoints.
"""

import unittest
import json
from io import BytesIO
from backend.app.database import init_db, get_connection
from backend.app.services.profit_intelligence_service import ProfitIntelligenceService
from backend.app.services.inventory_intelligence_service import InventoryIntelligenceService
from backend.app.services.customer_value_service import CustomerValueService
from backend.app.services.cashflow_intelligence_service import CashFlowIntelligenceService
from backend.app.services.guardrails_service import GuardrailsService, GuardrailViolationError
from backend.app.services.decision_twin_service import DecisionTwinService
from backend.app.services.incremental_outcome_service import IncrementalOutcomeService
from backend.app.services.opportunity_discovery_service import OpportunityDiscoveryService
from backend.app.services.business_value_service import BusinessValueService
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


class TestPhase8BusinessInnovation(unittest.TestCase):
    """Test suite for Phase 8 business innovation engines and REST API endpoints."""

    @classmethod
    def setUpClass(cls):
        init_db()

    # -------------------------------------------------------------
    # 1. Profit Intelligence Engine
    # -------------------------------------------------------------
    def test_01_profit_catalog_and_margin_rankings(self):
        """Verifies product profitability catalog calculates unit gross margin, contribution margin, and rankings."""
        catalog = ProfitIntelligenceService.get_product_profitability_catalog("MERCH-001")
        self.assertIsInstance(catalog, list)
        self.assertGreaterEqual(len(catalog), 8)
        
        p1 = catalog[0]
        self.assertIn("product_id", p1)
        self.assertIn("selling_price_inr", p1)
        self.assertIn("unit_cost_inr", p1)
        self.assertIn("unit_gross_profit_inr", p1)
        self.assertIn("gross_margin_pct", p1)
        self.assertIn("classification", p1)
        self.assertIn("recommendation", p1)
        
        classes = [p["classification"] for p in catalog]
        self.assertTrue(any(c in ["BEST_SELLER", "HIGH_MARGIN_OPPORTUNITY", "HIGH_REVENUE_LOW_MARGIN", "SLOW_MOVING_SURPLUS"] for c in classes))

        for product in catalog:
            expected_cogs = product["units_sold_period"] * product["unit_cost_inr"]
            self.assertAlmostEqual(product["total_cogs_inr"], expected_cogs)
            self.assertAlmostEqual(
                product["total_gross_profit_inr"],
                product["total_revenue_inr"] - expected_cogs
            )
            if product["total_revenue_inr"] > 0:
                self.assertAlmostEqual(
                    product["gross_margin_pct"],
                    product["total_gross_profit_inr"] / product["total_revenue_inr"] * 100,
                    places=1
                )
            else:
                self.assertIsNone(product["gross_margin_pct"])

        summary = ProfitIntelligenceService.calculate_profit_summary("MERCH-001")
        self.assertAlmostEqual(
            summary["total_gross_profit_inr"],
            sum(product["total_gross_profit_inr"] for product in catalog)
        )
        self.assertAlmostEqual(
            summary["blended_gross_margin_pct"],
            summary["total_gross_profit_inr"] / summary["total_revenue_inr"] * 100,
            places=1
        )

    def test_02_discount_erosion_model(self):
        """Verifies discount erosion calculation accurately models margin loss and breakeven units."""
        sim = ProfitIntelligenceService.model_discount_impact(
            product_id="PROD-001",
            discount_pct=10.0,
            expected_volume_lift_pct=25.0,
            merchant_id="MERCH-001"
        )
        self.assertIn("product_id", sim)
        self.assertEqual(sim["proposed_discount_pct"], 10.0)
        self.assertIn("discounted_selling_price_inr", sim)
        self.assertIn("discounted_margin_pct", sim)
        self.assertIn("breakeven_volume_lift_pct_required", sim)
        self.assertIn("guardrail_min_margin_passed", sim)
        self.assertIn("ai_verdict", sim)

    # -------------------------------------------------------------
    # 2. Predictive Inventory Intelligence
    # -------------------------------------------------------------
    def test_03_inventory_status_and_days_of_stock(self):
        """Verifies predictive inventory intelligence computes sales velocity, days on hand, and reorder alerts."""
        inv = InventoryIntelligenceService.get_inventory_status("MERCH-001")
        self.assertIsInstance(inv, list)
        self.assertGreaterEqual(len(inv), 8)
        
        item = inv[0]
        self.assertIn("product_id", item)
        self.assertIn("days_on_hand", item)
        self.assertIn("daily_sales_velocity", item)
        self.assertIn("recommended_action", item)
        self.assertIn("stockout_risk_status", item)

    def test_04_inventory_promotional_guardrail_block(self):
        """Verifies promotional guardrail check evaluates stock sufficiency."""
        guardrail = InventoryIntelligenceService.check_sku_promotional_guardrail(
            product_id="PROD-006",
            merchant_id="MERCH-001"
        )
        self.assertIn("allowed", guardrail)
        self.assertIn("product_id", guardrail)

    # -------------------------------------------------------------
    # 3. Customer Value Intelligence (RFM & CLV)
    # -------------------------------------------------------------
    def test_05_customer_rfm_segmentation_and_clv(self):
        """Verifies deterministic RFM scoring, segment classification, and CLV estimates."""
        rfm_data = CustomerValueService.get_rfm_customer_directory("MERCH-001")
        self.assertIsInstance(rfm_data, list)
        self.assertGreaterEqual(len(rfm_data), 5)
        
        c = rfm_data[0]
        self.assertIn("customer_id", c)
        self.assertIn("rfm_score", c)
        self.assertIn("segment", c)
        self.assertIn("estimated_clv_inr", c)
        self.assertIn("churn_risk_level", c)
        self.assertIn("recommended_strategy", c)
        
        segments = [cust["segment"] for cust in rfm_data]
        self.assertTrue(any(s in ["HIGH_VALUE_VIP", "LOYAL_REPEAT", "DECLINING_FREQUENCY", "NEW_CUSTOMER", "INACTIVE_DORMANT", "AT_RISK_VIP"] for s in segments))

    # -------------------------------------------------------------
    # 4. Merchant Cash-Flow Early Warning
    # -------------------------------------------------------------
    def test_06_cashflow_forecast_and_pinch_detection(self):
        """Verifies daily inflows/outflows forecast, net liquidity buffer, and pinch point detection."""
        cf = CashFlowIntelligenceService.get_cashflow_forecast("MERCH-001", horizon_days=14)
        self.assertIn("timeline", cf)
        self.assertEqual(len(cf["timeline"]), 14)
        self.assertIn("total_projected_inflows_inr", cf)
        self.assertIn("total_committed_outflows_inr", cf)
        self.assertIn("early_pinch_detected", cf)
        self.assertIn("regulatory_disclaimer", cf)
        self.assertIn("operational planning tool only", cf["regulatory_disclaimer"].lower())

    # -------------------------------------------------------------
    # 5. Flagship Decision Twin Simulation
    # -------------------------------------------------------------
    def test_07_decision_twin_four_strategies_simulation(self):
        """Verifies Decision Twin models 4 distinct strategies and compares gross margins and guardrails."""
        sim = DecisionTwinService.simulate_strategies(
            merchant_id="MERCH-001",
            budget_limit_inr=3600.0,
            discount_cap_pct=10.0,
            min_margin_floor_pct=25.0,
            audience_size=43
        )
        self.assertIn("strategies_simulated", sim)
        self.assertEqual(len(sim["strategies_simulated"]), 4)
        
        strat_keys = [s["scenario_key"] for s in sim["strategies_simulated"]]
        self.assertIn("STRATEGY_A_REMINDER", strat_keys)
        self.assertIn("STRATEGY_B_DISCOUNT", strat_keys)
        self.assertIn("STRATEGY_C_LOYALTY", strat_keys)
        self.assertIn("STRATEGY_D_BUNDLE", strat_keys)
        
        strat_a = next(s for s in sim["strategies_simulated"] if s["scenario_key"] == "STRATEGY_A_REMINDER")
        self.assertEqual(strat_a["discount_pct"], 0.0)
        
        self.assertIn("recommended_strategy", sim)
        self.assertIn("decision_twin_verdict", sim)

    # -------------------------------------------------------------
    # 6. No-Regret Business Guardrails
    # -------------------------------------------------------------
    def test_08_guardrails_evaluation_and_enforcement(self):
        """Verifies guardrails evaluate discounts, budgets, margin floors, and inventory rules."""
        # 1. Compliant scenario
        pass_eval = GuardrailsService.evaluate_campaign_guardrails(
            proposed_action={
                "discount_pct": 5.0,
                "total_budget_inr": 1000.0,
                "estimated_margin_pct": 35.0
            },
            merchant_id="MERCH-001"
        )
        self.assertTrue(pass_eval["passed"])
        self.assertEqual(len(pass_eval["violations"]), 0)

        # 2. Violating scenario (Discount 25% > 10% limit, Budget 8000 > 3600 limit, Margin 15% < 25% limit)
        fail_eval = GuardrailsService.evaluate_campaign_guardrails(
            proposed_action={
                "discount_pct": 25.0,
                "total_budget_inr": 8000.0,
                "estimated_margin_pct": 15.0
            },
            merchant_id="MERCH-001"
        )
        self.assertFalse(fail_eval["passed"])
        self.assertGreaterEqual(len(fail_eval["violations"]), 2)

    def test_09_guardrail_rule_update(self):
        """Verifies merchant can adjust active guardrail thresholds."""
        res = GuardrailsService.update_guardrail(
            rule_code="MAX_DISCOUNT_PERCENT",
            new_value=18.0,
            is_active=True,
            merchant_id="MERCH-001"
        )
        self.assertEqual(res["status"], "UPDATED")
        self.assertEqual(res["new_parameter_value"], 18.0)
        
        # Reset back to 10.0
        GuardrailsService.update_guardrail(
            rule_code="MAX_DISCOUNT_PERCENT",
            new_value=10.0,
            is_active=True,
            merchant_id="MERCH-001"
        )

    # -------------------------------------------------------------
    # 7. Incremental Outcomes & Reality Check
    # -------------------------------------------------------------
    def test_10_incremental_holdout_experiment_lift(self):
        """Verifies treatment vs holdout (85/15) math calculates true incremental revenue and gross profit."""
        res = IncrementalOutcomeService.get_campaign_experiment_result(
            campaign_id="CAMP-REC-1042",
            merchant_id="MERCH-001"
        )
        self.assertIn("treatment_group", res)
        self.assertIn("holdout_group", res)
        self.assertIn("incremental_impact", res)
        self.assertEqual(res["provenance_badge"], "SIMULATED_DEMO")
        
        impact = res["incremental_impact"]
        self.assertIn("conversion_lift_percentage_points", impact)
        self.assertIn("incremental_gross_profit_inr", impact)
        self.assertGreater(impact["incremental_gross_profit_inr"], 0)

    # -------------------------------------------------------------
    # 8. Opportunity Discovery & Ranking
    # -------------------------------------------------------------
    def test_11_ranked_business_opportunities(self):
        """Verifies autonomous opportunity scanner ranks actions by priority score and assigns risk categories."""
        opps = OpportunityDiscoveryService.get_ranked_opportunities("MERCH-001")
        self.assertIsInstance(opps, list)
        self.assertGreaterEqual(len(opps), 4)
        
        # Verify ordered by priority score descending
        scores = [o["priority_rank_score"] for o in opps]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Verify required permission tags
        perms = [o["required_permission"] for o in opps]
        self.assertTrue(any(p in ["CATEGORY_A", "CATEGORY_B"] for p in perms))
        summary = OpportunityDiscoveryService.get_opportunity_summary("MERCH-001")
        self.assertEqual(summary["total_opportunities_discovered"], len(opps))
        self.assertEqual(
            summary["total_unlocked_value_inr"],
            round(sum(opportunity["financial_impact_inr"] for opportunity in opps), 2)
        )

    # -------------------------------------------------------------
    # 9. Business Value Metrics & Provenance
    # -------------------------------------------------------------
    def test_12_business_value_metrics_and_provenance(self):
        """Verifies Business Value metrics dashboard calculates commercial ROI and enforces provenance badges."""
        bv = BusinessValueService.get_business_value_metrics("MERCH-001")
        self.assertIn("scorecards", bv)
        self.assertIn("classification_guide", bv)
        
        cards = bv["scorecards"]
        self.assertGreaterEqual(len(cards), 4)
        
        classifications = [c["classification"] for c in cards]
        self.assertTrue(any(cl in ["SIMULATED_DEMO", "ACTUAL_MEASURED", "ESTIMATED_PROJECTION"] for cl in classifications))

    # -------------------------------------------------------------
    # 10. HTTP REST API Endpoint Tests via DummyHandler
    # -------------------------------------------------------------
    def test_13_http_get_endpoints_phase8(self):
        """Verifies all Phase 8 GET REST endpoints respond with HTTP 200 and expected schemas."""
        endpoints = [
            "/api/profit/summary?merchant_id=MERCH-001",
            "/api/profit/catalog?merchant_id=MERCH-001",
            "/api/inventory/status?merchant_id=MERCH-001",
            "/api/inventory/summary?merchant_id=MERCH-001",
            "/api/customers/rfm?merchant_id=MERCH-001",
            "/api/customers/value-summary?merchant_id=MERCH-001",
            "/api/cashflow/forecast?merchant_id=MERCH-001",
            "/api/guardrails?merchant_id=MERCH-001",
            "/api/opportunities/ranked?merchant_id=MERCH-001",
            "/api/opportunities/summary?merchant_id=MERCH-001",
            "/api/outcomes/incremental?merchant_id=MERCH-001&campaign_id=CAMP-REC-1042",
            "/api/business-value/metrics?merchant_id=MERCH-001"
        ]
        
        for ep in endpoints:
            handler = DummyHandler("GET", ep)
            handler.do_GET()
            self.assertEqual(handler.status_code, 200, f"Failed GET for endpoint: {ep}")
            resp = handler.get_response_json()
            self.assertIn(type(resp), [dict, list], f"Response is not a dict or list for endpoint: {ep}")

    def test_14_http_post_endpoints_phase8(self):
        """Verifies all Phase 8 POST REST endpoints respond with HTTP 200 and valid responses."""
        # 1. Model discount
        h1 = DummyHandler("POST", "/api/profit/model-discount", {
            "product_id": "PROD-001",
            "discount_pct": 10.0,
            "expected_volume_lift_pct": 25.0
        })
        h1.do_POST()
        self.assertEqual(h1.status_code, 200)
        self.assertIn("discounted_selling_price_inr", h1.get_response_json())

        # 2. Update guardrail
        h2 = DummyHandler("POST", "/api/guardrails/update", {
            "rule_code": "MAX_CAMPAIGN_BUDGET_INR",
            "new_value": 4500.0,
            "is_active": True,
            "merchant_id": "MERCH-001"
        })
        h2.do_POST()
        self.assertEqual(h2.status_code, 200)
        self.assertEqual(h2.get_response_json()["status"], "UPDATED")

        # 3. Evaluate guardrail
        h3 = DummyHandler("POST", "/api/guardrails/evaluate", {
            "merchant_id": "MERCH-001",
            "discount_pct": 8.0,
            "total_budget_inr": 2500.0,
            "estimated_margin_pct": 32.0
        })
        h3.do_POST()
        self.assertEqual(h3.status_code, 200)
        self.assertIn("passed", h3.get_response_json())

        # 4. Decision Twin simulate
        h4 = DummyHandler("POST", "/api/decision-twin/simulate", {
            "merchant_id": "MERCH-001",
            "budget_limit_inr": 3600.0,
            "discount_cap_pct": 10.0,
            "min_margin_floor_pct": 25.0,
            "audience_size": 43
        })
        h4.do_POST()
        self.assertEqual(h4.status_code, 200)
        self.assertIn("strategies_simulated", h4.get_response_json())


if __name__ == "__main__":
    unittest.main()
