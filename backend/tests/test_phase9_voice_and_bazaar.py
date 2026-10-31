"""Phase 9 Comprehensive Test Suite:
Sarvam AI Voice Copilot & Bazaar Intelligence Network.
Verifies all 8 stages of the merchant growth journey:
Merchant conversation -> Business intelligence -> Neighbourhood demand discovery ->
Merchant-specific opportunity matching -> Profit simulation -> Merchant approval ->
Controlled execution -> Outcome verification.
"""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from backend.app.database import init_db, get_connection
from backend.app.services.voice_copilot_service import VoiceCopilotService
from backend.app.services.bazaar_intelligence_service import (
    BazaarIntelligenceService, LocalDemandSignalAgent, InventoryAndFulfilmentAgent,
    ProfitabilityAgent, CampaignStrategyAgent, RiskAndPrivacyGuardAgent, OutcomeVerificationAgent
)
from backend.tests.test_hackathon_demo_readiness import DummyHandler

class TestPhase9VoiceAndBazaar(unittest.TestCase):
    """Rigorous test suite for Phase 9: Voice Copilot and Bazaar Intelligence Network."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.voice_service = VoiceCopilotService()
        cls.bazaar_service = BazaarIntelligenceService()

    def test_01_voice_session_creation_and_persistence(self):
        """Verifies session lifecycle management and persistence for Hussain Fashion Store."""
        session = self.voice_service.create_or_get_session(merchant_id="MERCH-002", language_code="hi-IN")
        self.assertIsNotNone(session.get("session_id"))
        self.assertEqual(session.get("merchant_id"), "MERCH-002")
        self.assertEqual(session.get("language_code"), "hi-IN")
        self.assertEqual(session.get("status"), "ACTIVE")

        # Verify DB record
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM voice_sessions WHERE session_id = ?", (session["session_id"],))
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_02_voice_copilot_intent_detection_and_query_processing(self):
        """Tests natural Indic and English intent parsing across 7 core merchant business queries."""
        test_queries = [
            ("Why did my sales drop this week?", "SALES_DROP_ANALYSIS"),
            ("Mera sales kyu gira is hafte?", "SALES_DROP_ANALYSIS"),
            ("Which products have highest gross profit?", "PROFIT_ANALYSIS"),
            ("Kisme sabse zyada munafa hai?", "PROFIT_ANALYSIS"),
            ("What is my inventory risk?", "INVENTORY_STATUS"),
            ("Konsa stock fasa hua hai?", "INVENTORY_STATUS"),
            ("What is the local demand trend in Johari Bazaar?", "LOCAL_DEMAND_TREND"),
            ("Suggest a profitable campaign", "CAMPAIGN_RECOMMENDATION"),
            ("Compare 5% discount with bundle", "STRATEGY_COMPARISON"),
            ("How did my campaign perform?", "CAMPAIGN_PERFORMANCE")
        ]

        for query_text, expected_intent in test_queries:
            res = self.voice_service.process_query(
                merchant_id="MERCH-002",
                transcript=query_text,
                language_code="hi-IN",
                input_mode="VOICE"
            )
            self.assertEqual(res["detected_intent"], expected_intent, f"Failed for query: {query_text}")
            self.assertTrue(len(res["response_text"]) > 10)
            self.assertIsNotNone(res["structured_payload"])
            self.assertGreater(len(res["suggested_actions"]), 0)

    def test_voice_answer_does_not_speak_english_as_a_selected_indic_language(self):
        session = self.voice_service.create_or_get_session("MERCH-002", "ta-IN")
        with patch.object(self.voice_service.sarvam_client, "is_connected", return_value=False), \
             patch.object(self.voice_service, "synthesize_speech") as synthesize:
            result = self.voice_service.process_query(
                merchant_id="MERCH-002",
                transcript="Which products have highest gross profit?",
                language_code="ta-IN",
                input_mode="TEXT",
                session_id=session["session_id"]
            )

        self.assertIn("Set SARVAM_API_KEY", result["response_language_error"])
        self.assertIsNone(result["audio_base64"])
        synthesize.assert_not_called()

    def test_voice_answer_speaks_the_translated_selected_language(self):
        session = self.voice_service.create_or_get_session("MERCH-002", "ta-IN")
        tamil_reply = "உங்கள் விற்பனை நன்றாக உள்ளது."
        with patch.object(self.voice_service.sarvam_client, "is_connected", return_value=True), \
             patch.object(self.voice_service.sarvam_client, "post", return_value={
                 "translated_text": tamil_reply
             }), \
             patch.object(self.voice_service, "synthesize_speech", return_value={
                 "audio_base64": "UklGR-audio",
                 "provider": "SARVAM_BULBUL_LIVE"
             }) as synthesize:
            result = self.voice_service.process_query(
                merchant_id="MERCH-002",
                transcript="Which products have highest gross profit?",
                language_code="ta-IN",
                input_mode="TEXT",
                session_id=session["session_id"]
            )

        self.assertEqual(result["response_text"], tamil_reply)
        self.assertEqual(result["audio_base64"], "UklGR-audio")
        self.assertIsNone(result["response_language_error"])
        synthesize.assert_called_once_with(tamil_reply, "ta-IN")

    def test_03_voice_speech_synthesis_and_playable_audio(self):
        """Verifies a Bulbul audio response is returned without making a live API request."""
        sample_text = "नमस्ते ज़ुबैर जी, आपके स्टोर का ग्रॉस मार्जिन 48.5% है।"
        audio = "UklGR" + "A" * 120
        with patch.object(self.voice_service.sarvam_client, "is_connected", return_value=True), \
             patch.object(self.voice_service.tts, "generate_speech", return_value={
                 "audio_base64": audio,
                 "provider": "SARVAM_BULBUL_LIVE"
             }):
            synth = self.voice_service.synthesize_speech(sample_text, language_code="hi-IN")

        self.assertEqual(synth.get("audio_base64"), audio)
        self.assertEqual(synth.get("provider"), "SARVAM_BULBUL_LIVE")

    def test_04_bazaar_local_demand_pulse_and_k_anonymity_privacy_suppression(self):
        """Verifies small-cell cohort suppression (k >= 5) on neighbourhood demand signals."""
        pulse = LocalDemandSignalAgent.aggregate_signals("NEIGHBOURHOOD-JP-01")
        
        self.assertEqual(pulse["neighbourhood_id"], "NEIGHBOURHOOD-JP-01")
        self.assertEqual(pulse["min_cohort_threshold_k"], 5)
        self.assertGreaterEqual(pulse["total_signals_detected"], 2)

        signals = {s["signal_id"]: s for s in pulse["signals"]}
        
        # 1. Check Allowed / Published Signal (Cohort size = 7 >= 5)
        surge_signal = signals.get("SIG-JP-001")
        self.assertIsNotNone(surge_signal)
        self.assertFalse(surge_signal["privacy_suppressed"])
        self.assertGreaterEqual(surge_signal["reporting_merchants_count"], 5)
        self.assertEqual(surge_signal["growth_rate_pct"], 38.5)

        # 2. Check Suppressed Signal (Cohort size = 2 < 5)
        suppressed_signal = signals.get("SIG-JP-002")
        self.assertIsNotNone(suppressed_signal)
        self.assertTrue(suppressed_signal["privacy_suppressed"])
        self.assertLess(suppressed_signal["reporting_merchants_count"], 5)
        self.assertIn("Small Cell Suppression", suppressed_signal["suppression_reason"])

    def test_05_bazaar_participating_merchant_network_aggregation(self):
        """Verifies 14 participating merchants in Johari Bazaar cluster and category cohort rules."""
        net = self.bazaar_service.get_participating_network("NEIGHBOURHOOD-JP-01")
        self.assertEqual(net["total_participating_merchants"], 14)
        
        # Verify cohort breakdowns
        cohorts = {c["category"]: c for c in net["cohort_privacy_analysis"]}
        
        # Festive Ethnic Apparel (7 stores >= 5 -> PUBLISHED)
        self.assertIn("Festive Ethnic Apparel", cohorts)
        self.assertEqual(cohorts["Festive Ethnic Apparel"]["merchant_count"], 7)
        self.assertEqual(cohorts["Festive Ethnic Apparel"]["status"], "PUBLISHED")

        # Jewellery & Gems (5 stores >= 5 -> PUBLISHED)
        self.assertIn("Jewellery & Gems", cohorts)
        self.assertEqual(cohorts["Jewellery & Gems"]["merchant_count"], 5)
        self.assertEqual(cohorts["Jewellery & Gems"]["status"], "PUBLISHED")

        # Ceramics & Handicrafts (2 stores < 5 -> PRIVACY_SUPPRESSED)
        self.assertIn("Ceramics & Handicrafts", cohorts)
        self.assertEqual(cohorts["Ceramics & Handicrafts"]["merchant_count"], 2)
        self.assertEqual(cohorts["Ceramics & Handicrafts"]["status"], "PRIVACY_SUPPRESSED")

    def test_06_contextual_opportunity_matching_and_inventory_pairing(self):
        """Validates contextual opportunity matching score and inventory liquidation pairing."""
        opps = self.bazaar_service.get_contextual_opportunities("MERCH-002")
        self.assertGreaterEqual(len(opps), 1)

        match = opps[0]
        self.assertEqual(match["merchant_id"], "MERCH-002")
        self.assertEqual(match["signal_id"], "SIG-JP-001")
        self.assertEqual(match["matching_score"], 94.0)
        self.assertEqual(match["relevance_status"], "EXCELLENT")

        # Verify explainable score components
        breakdown = match["score_breakdown"]
        self.assertGreaterEqual(breakdown["product_relevance"], 90.0)
        self.assertGreaterEqual(breakdown["inventory_depth"], 90.0)
        self.assertGreaterEqual(breakdown["margin_headroom"], 90.0)
        self.assertGreaterEqual(breakdown["local_demand_momentum"], 90.0)

        # Verify inventory pairing (fast Kurta + 92-day aging Dupatta)
        prods = {p["product_id"]: p for p in match["compatible_products"]}
        self.assertIn("PROD-HFS-001", prods)
        self.assertIn("PROD-HFS-002", prods)
        self.assertEqual(prods["PROD-HFS-002"]["stock_age_days"], 92)
        self.assertEqual(prods["PROD-HFS-002"]["trapped_capital_inr"], 31080.0)

    def test_07_decision_twin_3_strategy_simulation_and_guardrails_gate(self):
        """Verifies Decision Twin models 3 strategies and enforces merchant guardrails."""
        # 1. Conservative (0% discount) -> Allowed
        sim_cons = self.bazaar_service.simulate_bazaar_opportunity("MERCH-002", "MATCH-HFS-001", "CONSERVATIVE")
        self.assertTrue(sim_cons["can_execute"])
        self.assertTrue(sim_cons["selected_scenario"]["guardrails_passed"])

        # 2. Balanced (8% discount) -> Allowed & Recommended
        sim_bal = self.bazaar_service.simulate_bazaar_opportunity("MERCH-002", "MATCH-HFS-001", "BALANCED")
        self.assertTrue(sim_bal["can_execute"])
        self.assertTrue(sim_bal["selected_scenario"]["guardrails_passed"])
        self.assertEqual(sim_bal["selected_scenario"]["discount_pct"], 8.0)
        self.assertEqual(sim_bal["selected_scenario"]["projected_gross_profit_inr"], 14406.0)

        # 3. Aggressive (18% discount) -> BLOCKED by Guardrail RULE-HFS-02 (max 10% discount)
        sim_agg = self.bazaar_service.simulate_bazaar_opportunity("MERCH-002", "MATCH-HFS-001", "AGGRESSIVE")
        self.assertFalse(sim_agg["can_execute"])
        self.assertFalse(sim_agg["selected_scenario"]["guardrails_passed"])
        self.assertGreater(len(sim_agg["selected_scenario"]["violations"]), 0)
        self.assertTrue(any("10" in v or "exceeds" in v for v in sim_agg["selected_scenario"]["violations"]))

    def test_08_bazaar_campaign_controlled_execution_and_hmac_signoff(self):
        """Verifies campaign execution creates HMAC signature, 85/15 holdout, and 7-point verification."""
        exec_res = self.bazaar_service.execute_bazaar_campaign(
            merchant_id="MERCH-002",
            match_id="MATCH-HFS-001",
            strategy_key="BALANCED",
            actor_name="Zubair Hussain (Store Owner)"
        )
        self.assertTrue(exec_res["success"])
        self.assertIsNotNone(exec_res.get("campaign_id"))
        self.assertIsNotNone(exec_res.get("execution_id"))
        self.assertEqual(len(exec_res["hmac_signature"]), 64)  # SHA-256 HMAC
        self.assertEqual(exec_res["verification_status"], "VERIFIED")

        # Verify 85/15 Treatment vs Holdout Split
        tot_aud = exec_res["treatment_audience"] + exec_res["holdout_audience"]
        self.assertEqual(tot_aud, 20)
        self.assertEqual(exec_res["treatment_audience"], 17)
        self.assertEqual(exec_res["holdout_audience"], 3)

        # Verify Soundbox Announcement Script
        self.assertIn("hi", exec_res["soundbox_announcement"])
        self.assertIn("en", exec_res["soundbox_announcement"])
        self.assertIn("हुसैन फैशन स्टोर", exec_res["soundbox_announcement"]["hi"])

        # Verify DB Records
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM campaign_drafts WHERE campaign_id = ?", (exec_res["campaign_id"],))
        self.assertEqual(cur.fetchone()[0], "COMPLETED")

        cur.execute("SELECT COUNT(*) FROM campaign_recipient_statuses WHERE campaign_id = ?", (exec_res["campaign_id"],))
        self.assertGreater(cur.fetchone()[0], 0)

        cur.execute("SELECT verification_status FROM verifications WHERE campaign_id = ?", (exec_res["campaign_id"],))
        self.assertEqual(cur.fetchone()[0], "VERIFIED")
        conn.close()

    def test_09_blocked_execution_on_guardrail_breach(self):
        """Verifies executing an aggressive strategy violating guardrails is strictly blocked."""
        exec_res = self.bazaar_service.execute_bazaar_campaign(
            merchant_id="MERCH-002",
            match_id="MATCH-HFS-001",
            strategy_key="AGGRESSIVE",
            actor_name="Zubair Hussain"
        )
        self.assertFalse(exec_res["success"])
        self.assertEqual(exec_res["error"], "GUARDRAIL_BLOCKED")
        self.assertIn("violations", exec_res)
        self.assertGreater(len(exec_res["violations"]), 0)

    def test_10_phase9_http_endpoints_via_dummy_handler(self):
        """Tests all GET and POST Phase 9 endpoints return HTTP 200 via DummyHandler."""
        endpoints_to_test = [
            ("GET", "/api/voice/session?merchant_id=MERCH-002", None),
            ("GET", "/api/voice/history?merchant_id=MERCH-002", None),
            ("GET", "/api/bazaar/pulse?neighbourhood_id=NEIGHBOURHOOD-JP-01", None),
            ("GET", "/api/bazaar/network?neighbourhood_id=NEIGHBOURHOOD-JP-01", None),
            ("GET", "/api/bazaar/opportunities?merchant_id=MERCH-002", None),
            ("POST", "/api/voice/transcribe", {"language_code": "hi-IN"}),
            ("POST", "/api/voice/chat", {"merchant_id": "MERCH-002", "transcript": "Why did my sales drop?", "language_code": "hi-IN"}),
            ("POST", "/api/voice/synthesize", {"text": "नमस्ते", "language_code": "hi-IN"}),
            ("POST", "/api/bazaar/simulate", {"merchant_id": "MERCH-002", "strategy_key": "BALANCED"}),
            ("POST", "/api/bazaar/execute", {"merchant_id": "MERCH-002", "strategy_key": "BALANCED"})
        ]

        for method, endpoint, body in endpoints_to_test:
            h = DummyHandler(method, endpoint, body)
            if method == "GET":
                h.do_GET()
            else:
                h.do_POST()
            self.assertEqual(h.status_code, 200, f"Failed {method} {endpoint}: {h.get_response_json()}")

    def test_11_end_to_end_phase9_voice_to_verified_outcome_journey(self):
        """Validates the full uninterrupted 8-stage merchant journey from voice query to verified outcome."""
        # 1. Merchant asks voice query: "What is the local demand trend?"
        h1 = DummyHandler("POST", "/api/voice/chat", {
            "merchant_id": "MERCH-002",
            "transcript": "What is the local demand trend in Johari Bazaar?",
            "language_code": "hi-IN"
        })
        h1.do_POST()
        self.assertEqual(h1.status_code, 200)
        q1_res = h1.get_response_json()
        self.assertEqual(q1_res["detected_intent"], "LOCAL_DEMAND_TREND")
        self.assertIn("38.5%", q1_res["response_text"])

        # 2. Demand Pulse shows surge (+38.5%) and suppresses pottery (k=2 < 5)
        h2 = DummyHandler("GET", "/api/bazaar/pulse?neighbourhood_id=NEIGHBOURHOOD-JP-01")
        h2.do_GET()
        self.assertEqual(h2.status_code, 200)
        pulse = h2.get_response_json()
        self.assertEqual(pulse["top_signal"]["growth_rate_pct"], 38.5)

        # 3. Contextual Opportunity matches Hussain Fashion Store inventory
        h3 = DummyHandler("GET", "/api/bazaar/opportunities?merchant_id=MERCH-002")
        h3.do_GET()
        self.assertEqual(h3.status_code, 200)
        opps = h3.get_response_json()
        self.assertEqual(opps[0]["matching_score"], 94.0)

        # 4. Decision Twin simulates Balanced Strategy and confirms Guardrails passed
        h4 = DummyHandler("POST", "/api/bazaar/simulate", {
            "merchant_id": "MERCH-002",
            "strategy_key": "BALANCED"
        })
        h4.do_POST()
        self.assertEqual(h4.status_code, 200)
        sim = h4.get_response_json()
        self.assertTrue(sim["can_execute"])

        # 5. Merchant approves & executes campaign with HMAC signoff
        h5 = DummyHandler("POST", "/api/bazaar/execute", {
            "merchant_id": "MERCH-002",
            "strategy_key": "BALANCED",
            "actor": "Zubair Hussain (Store Owner)"
        })
        h5.do_POST()
        self.assertEqual(h5.status_code, 200)
        exec_data = h5.get_response_json()
        self.assertTrue(exec_data["success"])
        self.assertEqual(exec_data["verification_status"], "VERIFIED")
        self.assertEqual(exec_data["treatment_audience"], 17)
        self.assertEqual(exec_data["holdout_audience"], 3)
        self.assertEqual(len(exec_data["hmac_signature"]), 64)

        # 6. Merchant asks Voice Copilot: "How did my campaign perform?"
        h6 = DummyHandler("POST", "/api/voice/chat", {
            "merchant_id": "MERCH-002",
            "transcript": "How did my campaign perform?",
            "language_code": "hi-IN"
        })
        h6.do_POST()
        self.assertEqual(h6.status_code, 200)
        perf_res = h6.get_response_json()
        self.assertEqual(perf_res["detected_intent"], "CAMPAIGN_PERFORMANCE")
        self.assertIn("लिफ्ट", perf_res["response_text"])

if __name__ == "__main__":
    unittest.main()
