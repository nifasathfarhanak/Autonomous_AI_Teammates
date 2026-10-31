import json
import unittest

from backend.app.database import init_db
from backend.app.services.sales_intelligence_service import get_sales_visualization_data
from backend.tests.test_hackathon_demo_readiness import DummyHandler


class TestSalesVisualization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_sales_visualization_uses_completed_order_records(self):
        result = get_sales_visualization_data(days=7)
        current_start = result["period"]["start_date"]
        current_end = result["period"]["end_date"]
        current_orders = [
            row for row in result["orders"]
            if current_start <= row["order_date"] <= current_end
        ]

        self.assertEqual(result["summary"]["current"]["order_count"], len(current_orders))
        self.assertAlmostEqual(
            result["summary"]["current"]["sales_inr"],
            sum(row["order_value"] for row in current_orders)
        )
        self.assertIn("items", current_orders[0])
        self.assertIn("customer_type", current_orders[0])
        self.assertGreaterEqual(result["summary"]["item_detail_coverage_pct"], 0)
        self.assertLessEqual(result["summary"]["item_detail_coverage_pct"], 100)
        self.assertFalse(result["gross_profit_available"])
        json.dumps(result)

    def test_custom_range_uses_matching_previous_period(self):
        result = get_sales_visualization_data(
            start_date="2026-10-24",
            end_date="2026-10-30"
        )

        self.assertEqual(result["period"]["days"], 7)
        self.assertEqual(result["period"]["previous_start_date"], "2026-10-17")
        self.assertEqual(result["period"]["previous_end_date"], "2026-10-23")

    def test_invalid_date_range_is_rejected(self):
        with self.assertRaises(ValueError):
            get_sales_visualization_data(start_date="2026-10-31", end_date="2026-10-01")

    def test_visualization_endpoint_rejects_unsupported_period(self):
        handler = DummyHandler("GET", "/api/sales/visualization?days=14")
        handler.do_GET()

        self.assertEqual(handler.status_code, 400)
        self.assertIn("7, 30, or 90", handler.get_response_json()["error"])


if __name__ == "__main__":
    unittest.main()
