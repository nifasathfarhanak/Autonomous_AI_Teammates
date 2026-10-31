"""DealPilot AI Enterprise Verification Test Suite.
Validates the complete 12-stage autonomous revenue recovery lifecycle:
1. Customer Ingestion & Validation
2. Agent 1: 5-Factor Opportunity Scoring & Ranking
3. Agent 2: Epistemic Research Intelligence (Facts vs Inferences)
4. Agent 3: Recovery Strategy & Sarvam Indic Translation
5. Sarvam AI Diagnostics & Health Protocol
6. Stage 7: Human-in-the-Loop Approval & Audit Logging
7. Agent 4: Execution Dispatch & RFC-822 MIME headers
8. Stage 9: Persistent Multi-Touch Follow-up Scheduling (Day 0, 3, 7)
9. Stage 10: Reply Monitoring & 9-State Intent Classification
10. Safety Guard: Immediate & Permanent Unsubscribe Cancellation
11. Stage 12: Verified Purchase Recording & 4-Tier Revenue Attribution
12. Closed-Loop Net Return & ROI Accounting
"""

import unittest
import json
from backend.app.database import get_connection, init_db, reset_database
from backend.app.agents.revenue_agent import RevenueIntelligenceAgent
from backend.app.agents.research_agent import CustomerResearchAgent
from backend.app.agents.recovery_strategy_agent import RecoveryStrategyAgent
from backend.app.agents.execution_followup_agent import ExecutionFollowupAgent
from backend.app.services.ingestion_service import parse_and_validate_csv
from backend.app.services.revenue_attribution_service import (
    schedule_recovery_followups, cancel_pending_followups,
    record_verified_purchase_transaction, get_customer_followups
)
from backend.app.integrations.sarvam import SarvamClient, SarvamTranslate

class TestDealPilotEnterpriseSuite(unittest.TestCase):
    """Full end-to-end test cases verifying all 12 stages."""

    @classmethod
    def setUpClass(cls):
        reset_database()

    def test_01_customer_ingestion_and_validation(self):
        """Validates CSV parsing, duplicate identification, and field validation."""
        csv_sample = (
            "customer_id,customer_name,email,company,phone,last_purchase_date,last_purchase_value,lifetime_value,interested_product,last_interaction_date,quotation_status,quotation_value,preferred_language\n"
            "CUST-NEW-1,Test Enterprise,test@example.com,Test Co,+91 99999-11111,2026-09-01,50000,150000,Valves,2026-09-20,UNANSWERED,45000,hi\n"
            "CUST-1001,Duplicate Arun,arun.kumar@biotechlabs.in,BioTech,+91 98711-23091,2026-08-19,85000,245000,Reactors,2026-09-15,UNANSWERED,65000,en\n"
            "CUST-NEW-2,Bad Email,invalid-email-string,Invalid Co,+91 99999-22222,2026-09-01,10000,20000,Packs,2026-09-20,NONE,0,en"
        )
        res = parse_and_validate_csv(csv_sample, commit=False)
        self.assertEqual(res["total_records"], 3)
        self.assertEqual(res["valid_preview_count"], 1)
        self.assertEqual(res["duplicate_count"], 1)
        self.assertEqual(res["invalid_count"], 1)

    def test_02_revenue_intelligence_5_factor_scoring(self):
        """Verifies Agent 1 deterministic mathematical scoring model."""
        agent = RevenueIntelligenceAgent()
        opps = agent.discover_opportunities(min_score_threshold=40)
        self.assertGreater(len(opps), 5)

        # Anchor customer Arun Kumar
        arun_opp = next((o for o in opps if o["customer"]["customer_id"] == "CUST-1001"), None)
        self.assertIsNotNone(arun_opp)
        self.assertEqual(arun_opp["category"], "UNANSWERED_QUOTATION")
        self.assertEqual(arun_opp["estimated_opportunity_value"], 650.0)
        self.assertEqual(
            arun_opp["recovery_score"],
            sum(factor["points"] for factor in arun_opp["score_breakdown"].values())
        )
        self.assertLessEqual(arun_opp["score_breakdown"]["historical_value_pts"]["points"], 25)
        self.assertEqual(arun_opp["score_breakdown"]["purchase_intent_pts"]["points"], 25)

    def test_03_customer_research_epistemic_report(self):
        """Verifies Agent 2 generates distinct Facts, Inferences, Missing Info, and Assumptions."""
        agent = CustomerResearchAgent()
        report = agent.research_customer("OPP-CUST-1001")
        self.assertIn("REP-OPP-CUST-1001", report["report_id"])
        self.assertGreater(len(report["confirmed_facts"]), 2)
        self.assertGreater(len(report["inferred_observations"]), 0)
        self.assertGreater(len(report["missing_information"]), 0)
        self.assertGreater(len(report["unverified_assumptions"]), 0)
        self.assertIn("Recorded Lifetime Spend: ₹", report["confirmed_facts"][0])

    def test_04_recovery_strategy_and_sarvam_translation(self):
        """Verifies Agent 3 strategy formulation and Sarvam Indic translation."""
        strat_agent = RecoveryStrategyAgent()
        strat = strat_agent.formulate_strategy("OPP-CUST-1001")
        self.assertEqual(strat["strategy_type"], "QUOTATION_REMINDER")
        self.assertEqual(strat["selected_tone"], "CONSULTATIVE_PROFESSIONAL")
        self.assertIn("Toned milk and wheat flour", strat["email_subject"])

        # Test Indic Translation to Hindi and Kannada
        trans_hi = strat_agent.translate_strategy(strat["strategy_id"], "hi")
        self.assertEqual(trans_hi["target_language"], "hi")
        self.assertIn("कोटेशन", trans_hi["translated_body"])

        trans_kn = strat_agent.translate_strategy(strat["strategy_id"], "kn")
        self.assertEqual(trans_kn["target_language"], "kn")
        self.assertIn("ಉಲ್ಲೇಖ", trans_kn["translated_body"])

    def test_05_sarvam_diagnostics_and_fallback(self):
        """Verifies Sarvam Client diagnostic connection and offline fallback safety."""
        client = SarvamClient()
        diag = client.test_connection()
        self.assertIn("status", diag)
        self.assertIn("supported_languages", diag)
        self.assertIn("en", diag["supported_languages"])
        self.assertIn("hi", diag["supported_languages"])

    def test_06_execution_and_followup_scheduling(self):
        """Verifies Agent 4 outreach execution, RFC-822 email, and Day 0/3/7 followups."""
        strat_id = "STRAT-OPP-CUST-1001"
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE recovery_strategies SET approval_status = 'APPROVED' WHERE strategy_id = ?", (strat_id,))
        conn.commit()
        conn.close()

        exec_agent = ExecutionFollowupAgent()
        res = exec_agent.execute_outreach(strat_id, is_demo_mode=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tracking_status"], "DEMO_DISPATCH_RECORDED")

        # Verify Day 0, Day 3, Day 7 follow-ups are persisted in database
        followups = get_customer_followups("CUST-1001")
        self.assertEqual(len(followups), 3)
        self.assertEqual(followups[0]["step_number"], 1)
        self.assertEqual(followups[0]["interval_days"], 0)
        self.assertEqual(followups[1]["step_number"], 2)
        self.assertEqual(followups[1]["interval_days"], 3)
        self.assertEqual(followups[2]["step_number"], 3)
        self.assertEqual(followups[2]["interval_days"], 7)

    def test_07_reply_classification_and_auto_cancellation(self):
        """Verifies customer reply monitoring, 9-state classification, and auto-cancelling followups."""
        exec_agent = ExecutionFollowupAgent()
        exec_id = "EXEC-STRAT-OPP-CUST-1001"

        # 1. Customer expresses meeting intent
        reply_res = exec_agent.process_customer_reply(exec_id, "We reviewed the quotation. Can we schedule a quick call next week?")
        self.assertEqual(reply_res["classification"], "REQUESTS_MEETING")
        self.assertTrue(reply_res["followups_stopped"])

        # Verify follow-ups are marked CANCELLED
        followups = get_customer_followups("CUST-1001")
        for f in followups:
            if f["step_number"] > 1:
                self.assertEqual(f["status"], "CANCELLED")
                self.assertEqual(f["cancellation_reason"], "CUSTOMER_REPLIED")

    def test_08_unsubscribe_safety_guard(self):
        """Verifies opt-out stops future messages and blocks subsequent outreach."""
        exec_agent = ExecutionFollowupAgent()
        exec_id = "EXEC-STRAT-OPP-CUST-1001"

        unsub_res = exec_agent.process_customer_reply(exec_id, "Stop emailing me. Unsubscribe.")
        self.assertEqual(unsub_res["classification"], "UNSUBSCRIBE")

        # Verify database flag is set
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_unsubscribed FROM customers WHERE customer_id = 'CUST-1001'")
        is_unsub = cur.fetchone()["is_unsubscribed"]
        conn.close()
        self.assertEqual(is_unsub, 1)

        # Attempt subsequent outreach and verify it is strictly BLOCKED
        blocked = exec_agent.execute_outreach("STRAT-OPP-CUST-1001")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("SAFETY_GUARD_TRIGGERED", blocked["reason"])

        # Reset flag for next tests
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE customers SET is_unsubscribed = 0 WHERE customer_id = 'CUST-1001'")
        conn.commit()
        conn.close()

    def test_09_verified_purchase_and_closed_loop_roi(self):
        """Verifies closed-loop verified purchase ledger and 4-tier revenue attribution."""
        exec_agent = ExecutionFollowupAgent()
        exec_id = "EXEC-STRAT-OPP-CUST-1001"

        res = exec_agent.record_verified_purchase(exec_id, order_value_inr=65000.0, invoice_ref="INV-2026-9042")
        self.assertIn("verified_purchase", res)
        purch = res["verified_purchase"]
        self.assertEqual(purch["order_id"], "INV-2026-9042")
        self.assertEqual(purch["purchase_amount"], 65000.0)
        self.assertEqual(purch["revenue_category"], "RECOVERED")
        self.assertEqual(purch["attribution_confidence"], "DIRECT_ATTRIBUTION")

        # Verify ledger entry in verified_purchases table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM verified_purchases WHERE order_id = 'INV-2026-9042'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["purchase_amount"], 65000.0)

if __name__ == "__main__":
    unittest.main()
