"""Paytm AI ActionMate Phase 2 Automated Test Suite.
Validates the merchant data layer, sales analytics engine, 4-week repeat purchase trends,
deterministic sales drop detection, customer segmentation, data APIs, and persistence.
"""

import io
import json
import sqlite3
import unittest
from backend.app.server import DealPilotRequestHandler
from backend.app.database import init_db, get_connection
from backend.app.services.sales_intelligence_service import (
    get_merchant_profile,
    calculate_sales_summary,
    calculate_repeat_analysis,
    detect_sales_drop,
    get_customer_segments,
    get_product_performance,
    get_customer_purchase_history,
    seed_sales_transactions
)

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

class TestSalesIntelligencePhase2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_merchant_business_profile(self):
        """Validates demo merchant profile adheres to specifications with DEMO flag."""
        profile = get_merchant_profile("MERCH-001")
        self.assertEqual(profile.id, "MERCH-001")
        self.assertEqual(profile.store_name, "Sharma Family Grocery")
        self.assertEqual(profile.owner_name, "Ramesh Sharma")
        self.assertEqual(profile.category, "Neighborhood Grocery")
        self.assertEqual(profile.soundbox_device_id, "SB-4G-DEL-9842")
        self.assertEqual(profile.soundbox_status, "ONLINE")
        self.assertIn("DEMO", profile.gstin_demo)

    def test_02_sales_daily_weekly_figures_match_spec(self):
        """Verifies daily and weekly sales figures strictly match PPT figures:
        Last week: 52, 55, 50, 58, 61, 70, 66 (Total: 412k)
        This week: 51, 49, 44, 40, 38, 41, 37 (Total: 300k)
        """
        summary = calculate_sales_summary("MERCH-001")
        self.assertEqual(summary.last_week_total_k, 412.0)
        self.assertEqual(summary.this_week_total_k, 300.0)
        self.assertEqual(summary.overall_drop_pct, -27.2)
        self.assertEqual(summary.absolute_difference_inr, 112000.0)
        self.assertTrue(summary.is_demo)

        expected_last_week = [52.0, 55.0, 50.0, 58.0, 61.0, 70.0, 66.0]
        expected_this_week = [51.0, 49.0, 44.0, 40.0, 38.0, 41.0, 37.0]

        breakdown = summary.daily_breakdown
        self.assertEqual(len(breakdown), 7)
        for i, item in enumerate(breakdown):
            self.assertEqual(item["last_week"], expected_last_week[i])
            self.assertEqual(item["this_week"], expected_this_week[i])

    def test_03_repeat_purchase_percentages_four_weeks(self):
        """Verifies repeat customer order percentages match PPT specification:
        Week 1: 41%, Week 2: 39%, Week 3: 37%, Week 4: 24%
        """
        repeat_analysis = calculate_repeat_analysis("MERCH-001")
        self.assertEqual(repeat_analysis.week_1_pct, 41.0)
        self.assertEqual(repeat_analysis.week_2_pct, 39.0)
        self.assertEqual(repeat_analysis.week_3_pct, 37.0)
        self.assertEqual(repeat_analysis.week_4_pct, 24.0)
        self.assertEqual(repeat_analysis.drop_percentage_points, -13.0)
        self.assertEqual(repeat_analysis.relative_drop_pct, -35.1)
        self.assertEqual(repeat_analysis.unreturned_regular_patrons, 46)
        self.assertEqual(repeat_analysis.revenue_at_risk_inr, 20900.0)

    def test_04_deterministic_sales_drop_detection(self):
        """Verifies sales drop detection service calculates exact drop metrics and diagnostic evidence."""
        drop = detect_sales_drop("MERCH-001")
        self.assertTrue(drop.is_drop_detected)
        self.assertEqual(drop.drop_severity, "HIGH")
        self.assertEqual(drop.sales_difference_inr, 112000.0)
        self.assertEqual(drop.sales_percentage_difference, -27.2)
        self.assertEqual(drop.repeat_purchase_change_pts, -13.0)
        self.assertGreaterEqual(len(drop.supporting_evidence), 5)
        self.assertIn("do not establish why", drop.explanation)

    def test_05_customer_segmentation(self):
        """Verifies customer segmentation groups into Repeat, New, Inactive, High-Value, and Declining."""
        segments = get_customer_segments("MERCH-001")
        self.assertEqual(len(segments), 5)

        segment_keys = [s.segment_key for s in segments]
        self.assertIn("REPEAT", segment_keys)
        self.assertIn("NEW", segment_keys)
        self.assertIn("INACTIVE", segment_keys)
        self.assertIn("HIGH_VALUE", segment_keys)
        self.assertIn("DECLINING_FREQUENCY", segment_keys)

        for s in segments:
            self.assertGreater(s.customer_count, 0)
            self.assertGreater(s.total_segment_ltv_inr, 0)
            self.assertGreater(len(s.sample_customers), 0)

        declining = next(s for s in segments if s.segment_key == "DECLINING_FREQUENCY")
        self.assertEqual(declining.customer_count, 46)

    def test_06_product_performance(self):
        """Verifies product performance metrics calculate orders and revenue accurately."""
        products = get_product_performance("MERCH-001")
        self.assertGreaterEqual(len(products), 5)
        for p in products:
            self.assertTrue(p.product_id.startswith("PROD-"))
            self.assertGreater(p.unit_price, 0)
            self.assertGreater(p.units_sold_30d, 0)
            self.assertGreater(p.gross_revenue_inr, 0)
            self.assertGreater(p.repeat_order_rate_pct, 0)

    def test_07_customer_purchase_history_and_invalid_id(self):
        """Verifies retrieving customer order history and graceful handling of nonexistent IDs."""
        # Valid customer
        cust_orders = get_customer_purchase_history("CUST-1001")
        self.assertIn("customer", cust_orders)
        self.assertEqual(cust_orders["customer"]["customer_id"], "CUST-1001")
        self.assertIn("orders", cust_orders)
        self.assertGreaterEqual(len(cust_orders["orders"]), 1)

        # Invalid customer ID
        invalid_orders = get_customer_purchase_history("CUST-NONEXISTENT-999")
        self.assertEqual(invalid_orders, {})

    def test_08_all_data_apis_via_http_handler(self):
        """Verifies all Phase 2 Data API endpoints respond with 200 OK and valid JSON."""
        endpoints = [
            "/api/merchant/profile",
            "/api/sales/summary",
            "/api/sales/trends",
            "/api/sales/repeat-analysis",
            "/api/sales/drop-detection",
            "/api/products/performance",
            "/api/customers/segments",
            "/api/customers/CUST-1001/orders",
            "/api/business/insights"
        ]

        for path in endpoints:
            h = DummyHandler(path, method="GET")
            self.assertTrue(h.wfile.getvalue().startswith(b"HTTP/1.0 200 OK") or
                            h.wfile.getvalue().startswith(b"HTTP/1.1 200 OK"),
                            f"Endpoint {path} failed with response: {h.wfile.getvalue()[:100]}")
            data = get_response_data(h)
            self.assertIsInstance(data, dict if not path.endswith("performance") and not path.endswith("segments") else list)

    def test_09_database_persistence_and_deterministic_seeding(self):
        """Verifies sales data persists across database connection cycles and tables remain consistent."""
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM orders")
        order_count = c.fetchone()[0]
        self.assertEqual(order_count, 901)

        c.execute("SELECT COUNT(*) FROM order_items")
        items_count = c.fetchone()[0]
        self.assertGreaterEqual(items_count, 42)

        # Re-running seed_sales_transactions idempotently preserves row count
        seed_sales_transactions(conn)
        c.execute("SELECT COUNT(*) FROM orders")
        self.assertEqual(c.fetchone()[0], 901)
        conn.close()

if __name__ == "__main__":
    unittest.main()
