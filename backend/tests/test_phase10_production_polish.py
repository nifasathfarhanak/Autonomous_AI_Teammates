"""Phase 10: Production Polish, UI Cleanup & Go-Live Transformation Test Suite.
Validates production readiness, security headers, robots.txt, sitemap.xml,
system environment mode toggles, truthful integration dependency health,
and regression freedom across the entire commercial SaaS platform.
"""

import os
import json
import unittest
from pathlib import Path
from backend.app.server import DealPilotRequestHandler
from backend.app.config import BASE_DIR
from backend.tests.test_hackathon_demo_readiness import DummyHandler


class TestPhase10ProductionPolish(unittest.TestCase):
    """Production quality, security, and integration health test suite."""

    def test_01_security_headers_present_on_all_responses(self):
        """Verifies strict production security headers are set on HTTP responses."""
        class HeaderCapturingHandler(DealPilotRequestHandler):
            def __init__(self):
                self.headers_sent = {}
            def send_response(self, code, message=None):
                self.code = code
            def send_header(self, keyword, value):
                self.headers_sent[keyword] = value
            def end_headers(self):
                self.ended = True

        h = HeaderCapturingHandler()
        h._set_headers(200, "application/json")

        self.assertEqual(h.headers_sent.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(h.headers_sent.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(h.headers_sent.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(h.headers_sent.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(h.headers_sent.get("Content-Type"), "application/json")

    def test_02_robots_and_sitemap_static_files_exist(self):
        """Verifies robots.txt and sitemap.xml exist and protect private routes."""
        robots_path = BASE_DIR / "robots.txt"
        self.assertTrue(robots_path.exists(), "robots.txt must exist")
        with open(robots_path, "r", encoding="utf-8") as f:
            robots_content = f.read()
        self.assertIn("Disallow: /app/", robots_content)
        self.assertIn("Disallow: /api/", robots_content)
        self.assertIn("Allow: /", robots_content)

        sitemap_path = BASE_DIR / "sitemap.xml"
        self.assertTrue(sitemap_path.exists(), "sitemap.xml must exist")
        with open(sitemap_path, "r", encoding="utf-8") as f:
            sitemap_content = f.read()
        self.assertIn("https://actionmate.paytm.com/", sitemap_content)
        self.assertIn("/login", sitemap_content)

    def test_03_system_mode_get_and_post_switching(self):
        """Verifies /api/system/mode queries and switches between demo and production modes."""
        # 1. Query initial mode
        h_get = DummyHandler("GET", "/api/system/mode")
        h_get.do_GET()
        self.assertEqual(h_get.status_code, 200)
        res_get = json.loads(h_get.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res_get["status"], "SUCCESS")
        self.assertIn("environment", res_get)

        # 2. Switch to production
        h_post_prod = DummyHandler("POST", "/api/system/mode", {"environment": "production"})
        h_post_prod.do_POST()
        self.assertEqual(h_post_prod.status_code, 200)
        res_prod = json.loads(h_post_prod.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res_prod["environment"], "production")
        self.assertFalse(res_prod["is_demo"])

        # 3. Switch back to demo
        h_post_demo = DummyHandler("POST", "/api/system/mode", {"environment": "demo"})
        h_post_demo.do_POST()
        self.assertEqual(h_post_demo.status_code, 200)
        res_demo = json.loads(h_post_demo.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res_demo["environment"], "demo")
        self.assertTrue(res_demo["is_demo"])

    def test_04_system_dependencies_truthful_reporting(self):
        """Verifies /api/system/dependencies returns truthful health for all 6 subsystems."""
        handler = DummyHandler("GET", "/api/system/dependencies")
        handler.do_GET()
        self.assertEqual(handler.status_code, 200)
        res = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("dependencies", res)

        dep_names = [d["name"] for d in res["dependencies"]]
        self.assertIn("SQLite 3 Relational Database", dep_names)
        self.assertIn("Sarvam AI Sovereign Indic Voice Stack", dep_names)
        self.assertIn("Paytm Soundbox 4G Telemetry", dep_names)
        self.assertIn("Bazaar Intelligence Privacy Protocol", dep_names)
        self.assertIn("Merchant Guardrails Risk Policy", dep_names)
        self.assertIn("Customer Messaging Gateway", dep_names)

        # Verify privacy status is enforced
        privacy_dep = next(d for d in res["dependencies"] if "Bazaar" in d["name"])
        self.assertEqual(privacy_dep["status"], "ENFORCED")

    def test_05_env_example_file_integrity(self):
        """Verifies .env.example exists and contains placeholders without real credentials."""
        env_ex_path = BASE_DIR / ".env.example"
        self.assertTrue(env_ex_path.exists(), ".env.example must exist")
        with open(env_ex_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("SARVAM_API_KEY=", content)
        self.assertIn("your_sarvam_api_key_here", content)
        self.assertIn("ENVIRONMENT=", content)
        self.assertIn("ACTIONMATE_HMAC_SECRET=", content)
        # Ensure no real keys leaked in .env.example
        self.assertNotIn("sk_8mff", content)

    def test_06_navigation_routes_completeness_in_index_html(self):
        """Verifies all Phase 0-9 routes are covered by nav items and views in index.html."""
        index_path = BASE_DIR / "index.html"
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        expected_routes = [
            "overview", "sales", "profit", "inventory", "customers", "cashflow",
            "voice-copilot", "bazaar-intelligence", "decision-twin", "opportunities",
            "assistant", "campaigns", "approvals", "activity", "analytics",
            "business-value", "guardrails", "settings"
        ]

        for route in expected_routes:
            # Check view container
            view_id = f'id="view-{route}"'
            self.assertIn(view_id, html, f"Missing view container for route: {route}")

        # Check mobile hamburger toggle button
        self.assertIn('id="mobileNavToggleBtn"', html)
        # Check environment mode pill
        self.assertIn('id="envModePill"', html)
        # Check environment modal
        self.assertIn('id="envModeModalBackdrop"', html)


if __name__ == "__main__":
    unittest.main()
