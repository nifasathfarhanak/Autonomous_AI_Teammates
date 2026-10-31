"""DealPilot AI End-to-End Automated Test Suite.
Validates all 4 AI agents and the complete 5-stage Autonomous Customer Revenue Recovery workflow.
"""

import unittest
import json
from backend.app.database import init_db, get_connection, generate_sample_csv_text
from backend.app.services.ingestion_service import parse_and_validate_csv
from backend.app.agents.revenue_agent import RevenueIntelligenceAgent
from backend.app.agents.research_agent import CustomerResearchAgent
from backend.app.agents.recovery_strategy_agent import RecoveryStrategyAgent
from backend.app.agents.execution_followup_agent import ExecutionFollowupAgent
from backend.app.services.roi_service import simulate_and_verify_roi
from backend.app.fsm import approve_workflow, reset_to_initial_state

class TestDealPilotWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        # Seed opportunities so downstream tests have opportunities table populated
        agent = RevenueIntelligenceAgent()
        agent.discover_opportunities(min_score_threshold=40)

    def test_stage_1_csv_ingestion_and_validation(self):
        """Test Stage 1: CSV sample parsing, validation rules, duplicate detection, and import preview."""
        sample_csv = generate_sample_csv_text()
        
        # Test preview without commit
        preview = parse_and_validate_csv(sample_csv, commit=False)
        self.assertEqual(preview["total_records"], 5)
        self.assertGreaterEqual(preview["valid_preview_count"], 0)
        self.assertFalse(preview["is_committed"])

        # Test invalid email format rejection
        bad_csv = "customer_id,customer_name,email,company,phone,last_purchase_date,last_purchase_value,lifetime_value,interested_product,last_interaction_date,quotation_status,quotation_value,preferred_language\nCUST-999,Bad Email,not-an-email,ACME,+91 99999-99999,2026-10-01,1000,2000,Test,2026-10-10,NONE,0,en"
        bad_preview = parse_and_validate_csv(bad_csv, commit=False)
        self.assertEqual(bad_preview["invalid_count"], 1)

    def test_stage_2_revenue_intelligence_agent(self):
        """Test Stage 2: Agent 1 opportunity discovery and 5-factor mathematical scoring model."""
        agent = RevenueIntelligenceAgent()
        opps = agent.discover_opportunities(min_score_threshold=40)
        
        self.assertGreater(len(opps), 0)
        top_opp = opps[0]
        
        # Check scoring breakdown keys
        score = top_opp["recovery_score"]
        self.assertGreaterEqual(score, 40)
        self.assertLessEqual(score, 100)
        
        breakdown = top_opp["score_breakdown"]
        self.assertIn("historical_value_pts", breakdown)
        self.assertIn("purchase_intent_pts", breakdown)
        self.assertIn("recency_interaction_pts", breakdown)
        self.assertIn("outstanding_quotation_pts", breakdown)
        self.assertIn("engagement_history_pts", breakdown)
        
        # Verify Arun Kumar test case (matches example in specification)
        arun_opp = next((o for o in opps if "Arun Kumar" in o["customer"]["customer_name"]), None)
        self.assertIsNotNone(arun_opp)
        self.assertEqual(arun_opp["category"], "UNANSWERED_QUOTATION")
        self.assertEqual(arun_opp["estimated_opportunity_value"], 65000.0)
        self.assertGreaterEqual(arun_opp["recovery_score"], 85)

    def test_stage_3_customer_research_agent(self):
        """Test Stage 3: Agent 2 Customer Research report with verified facts vs missing info."""
        agent = CustomerResearchAgent()
        report = agent.research_customer("OPP-CUST-1001")
        
        self.assertEqual(report["customer_id"], "CUST-1001")
        self.assertGreater(len(report["confirmed_facts"]), 0)
        self.assertGreater(len(report["inferred_observations"]), 0)
        self.assertGreater(len(report["missing_information"]), 0)
        self.assertGreater(len(report["unverified_assumptions"]), 0)

    def test_stage_4_recovery_strategy_agent(self):
        """Test Stage 4 & 5: Agent 3 strategy formulation, tone, and human editability."""
        agent = RecoveryStrategyAgent()
        strat = agent.formulate_strategy("OPP-CUST-1001")
        
        self.assertEqual(strat["strategy_type"], "QUOTATION_REMINDER")
        self.assertEqual(strat["selected_tone"], "CONSULTATIVE_PROFESSIONAL")
        self.assertIn("Quotation Value: ₹65,000", strat["email_body"])
        self.assertEqual(strat["potential_commercial_value"], 65000.0)

        # Test human editing
        new_subj = "Updated: Following up on your custom laboratory quotation — Arun Kumar"
        new_body = "Dear Arun,\n\nChecking in on the laboratory accessories quotation.\nBest,\nRamesh"
        agent.update_draft(strat["strategy_id"], new_subj, new_body)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT email_subject, is_user_edited FROM recovery_strategies WHERE strategy_id = ?", (strat["strategy_id"],))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["email_subject"], new_subj)
        self.assertEqual(row["is_user_edited"], 1)

    def test_stage_5_execution_and_followup_agent(self):
        """Test Stage 6 & 7: Agent 4 execution, unsubscribe safety guard, and reply classification."""
        strat_agent = RecoveryStrategyAgent()
        strat = strat_agent.formulate_strategy("OPP-CUST-1001")
        strat_id = strat["strategy_id"]
        
        # Approve strategy first (HITL requirement)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE recovery_strategies SET approval_status = 'APPROVED' WHERE strategy_id = ?", (strat_id,))
        conn.commit()
        conn.close()

        exec_agent = ExecutionFollowupAgent()
        res = exec_agent.execute_outreach(strat_id, is_demo_mode=False)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tracking_status"], "DELIVERED")

        exec_id = res["execution_id"]

        # Test reply classification: Requests Meeting
        reply_res = exec_agent.process_customer_reply(exec_id, "Can we schedule a call next Tuesday to discuss?")
        self.assertEqual(reply_res["classification"], "REQUESTS_MEETING")

        # Test Unsubscribe Safety Guard: Ensure opt-out stops future messages
        unsub_res = exec_agent.process_customer_reply(exec_id, "Please remove me from your list. Unsubscribe.")
        self.assertEqual(unsub_res["classification"], "UNSUBSCRIBE")

        # Verify subsequent outreach is blocked
        blocked_res = exec_agent.execute_outreach(strat_id)
        self.assertEqual(blocked_res["status"], "BLOCKED")
        self.assertIn("SAFETY_GUARD_TRIGGERED", blocked_res["reason"])

        # Reset customer unsubscribe for subsequent tests
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE customers SET is_unsubscribed = 0 WHERE customer_id = 'CUST-1001'")
        conn.commit()
        conn.close()

    def test_verified_closed_loop_roi_calculation(self):
        """Test verified ROI calculation based on transaction attribution."""
        roi = simulate_and_verify_roi("WF-REC-1042", redemption_count=44, avg_ticket_inr=385.0)
        self.assertEqual(roi["gross_recovered_sales_inr"], 16940.0)
        self.assertEqual(roi["total_discounts_paid_inr"], 2200.0)
        self.assertEqual(roi["net_recovered_profit_inr"], 14644.0)
        self.assertEqual(roi["roi_multiple"], 6.38)
        self.assertTrue(roi["is_verified"])

if __name__ == "__main__":
    unittest.main()
