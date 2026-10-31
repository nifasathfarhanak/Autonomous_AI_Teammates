"""Paytm AI ActionMate Phase 3 Automated Test Suite.
Validates the central autonomous AI orchestrator, natural-language task understanding,
epistemic reasoning engine, 10-step planner, controlled tool registry,
14-state task state machine, argument validation, and persistence.
"""

import json
import unittest
from backend.app.database import init_db, get_connection
from backend.app.schemas import TaskSchema, PlanStepSchema, EpistemicReportSchema
from backend.app.orchestrator import (
    orchestrator, registry, IntentAnalyzer, ReasoningEngine, TaskPlanner,
    transition_task_state, validate_state_transition, StateTransitionError,
    get_task_state_history, STATE_RECEIVED, STATE_UNDERSTANDING, STATE_RETRIEVING_CONTEXT,
    STATE_ANALYSING, STATE_PLANNING, STATE_READY_FOR_APPROVAL, STATE_APPROVED,
    STATE_EXECUTING, STATE_VERIFYING, STATE_COMPLETED, STATE_REQUIRES_HUMAN,
    STATE_FAILED, STATE_CANCELLED
)
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

class TestOrchestratorPhase3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_natural_language_intent_analysis(self):
        """Verifies natural-language request parsing into structured intent and required context."""
        request_text = "My sales have dropped this week. Help me bring customers back."
        analysis = IntentAnalyzer.analyze_request(request_text, merchant_id="MERCH-001")

        self.assertEqual(analysis["detected_intent"], "SALES_RECOVERY_REENGAGEMENT")
        self.assertGreaterEqual(analysis["confidence"], 0.90)
        self.assertEqual(analysis["risk_classification"], "MEDIUM")
        self.assertTrue(analysis["approval_requirements"]["requires_merchant_approval"])
        self.assertEqual(analysis["approval_requirements"]["max_authorized_budget_inr"], 3600.0)
        self.assertIn("weekly_sales_this_week", analysis["required_data"])
        self.assertIn("repeat_purchase_trend_4_weeks", analysis["required_data"])
        self.assertEqual(analysis["provider"], "DETERMINISTIC_REASONING_ENGINE")
        self.assertTrue(analysis["is_demo"])

        # Test generic assistance request fallback
        generic_analysis = IntentAnalyzer.analyze_request("What are my store opening hours?")
        self.assertEqual(generic_analysis["detected_intent"], "GENERAL_BUSINESS_ASSISTANCE")
        self.assertEqual(generic_analysis["risk_classification"], "LOW")
        self.assertFalse(generic_analysis["approval_requirements"]["requires_merchant_approval"])

    def test_02_structured_task_generation_and_schema_validation(self):
        """Verifies orchestrator builds a valid TaskSchema with a 10-step plan."""
        task_id = "WF-REC-P3-TEST-01"
        task = orchestrator.create_task_from_request(
            user_request="My sales have dropped this week. Help me bring customers back.",
            merchant_id="MERCH-001",
            task_id=task_id
        )

        self.assertIsInstance(task, TaskSchema)
        self.assertEqual(task.task_id, task_id)
        self.assertEqual(task.merchant_id, "MERCH-001")
        self.assertEqual(task.current_state, STATE_READY_FOR_APPROVAL)
        self.assertEqual(task.risk_classification, "MEDIUM")

        # 10-Step Plan Verification
        plan = task.plan
        self.assertEqual(len(plan), 10)
        self.assertEqual(plan[0].step_id, "step_1_get_weekly_sales")
        self.assertEqual(plan[1].step_id, "step_2_compare_sales_periods")
        self.assertEqual(plan[2].step_id, "step_3_get_repeat_purchase_trend")
        self.assertEqual(plan[3].step_id, "step_4_get_customer_segments")
        self.assertEqual(plan[4].step_id, "step_5_recommend_campaign")
        self.assertEqual(plan[5].step_id, "step_6_draft_messages")
        self.assertEqual(plan[6].step_id, "step_7_request_approval")
        self.assertEqual(plan[7].step_id, "step_8_simulate_execution")
        self.assertEqual(plan[8].step_id, "step_9_verify_execution")
        self.assertEqual(plan[9].step_id, "step_10_report_outcome")

        # Step 7 is mandatory human approval gate
        step_7 = plan[6]
        self.assertTrue(step_7.requires_approval)
        self.assertEqual(step_7.risk_level, "HIGH")
        self.assertEqual(step_7.status, "PENDING_APPROVAL")

    def test_03_context_retrieval_all_nine_tools(self):
        """Verifies all 9 context retrieval tools execute through the registry and return real data."""
        tools_to_test = [
            ("get_merchant_profile", {"merchant_id": "MERCH-001"}),
            ("get_sales_summary", {"merchant_id": "MERCH-001"}),
            ("get_weekly_sales", {"merchant_id": "MERCH-001", "period": "this_week"}),
            ("compare_sales_periods", {"merchant_id": "MERCH-001"}),
            ("get_repeat_purchase_trend", {"merchant_id": "MERCH-001"}),
            ("get_customer_segments", {"merchant_id": "MERCH-001"}),
            ("get_top_customers", {"merchant_id": "MERCH-001", "limit": 5}),
            ("get_product_performance", {"merchant_id": "MERCH-001"}),
            ("get_campaign_history", {"merchant_id": "MERCH-001"})
        ]

        for tool_name, args in tools_to_test:
            res = registry.execute(tool_name, args)
            self.assertEqual(res.status, "SUCCESS", f"Tool '{tool_name}' failed: {res.error_message}")
            self.assertIsNotNone(res.data)
            self.assertGreater(res.execution_duration_ms, 0)
            self.assertTrue(res.verified)

    def test_04_tool_registry_permission_enforcement(self):
        """Verifies tool registry enforces permissions and prevents unauthorized calls."""
        # Call with insufficient permissions
        res = registry.execute("compare_sales_periods", {"merchant_id": "MERCH-001"}, caller_permissions=["UNAUTHORIZED_ROLE"])
        self.assertEqual(res.status, "PERMISSION_DENIED")
        self.assertIn("lacks required permission", res.error_message)

        # Call unregistered tool
        res_unregistered = registry.execute("unregistered_arbitrary_shell_tool", {})
        self.assertEqual(res_unregistered.status, "FAILED")
        self.assertIn("not registered", res_unregistered.error_message)

    def test_05_tool_argument_validation(self):
        """Verifies argument validation catches missing required parameters and invalid types."""
        # Missing required parameter 'merchant_id'
        res_missing = registry.execute("get_merchant_profile", {})
        self.assertEqual(res_missing.status, "VALIDATION_ERROR")
        self.assertIn("Missing required argument 'merchant_id'", res_missing.error_message)

        # Invalid type for period (should be string)
        res_type = registry.execute("get_weekly_sales", {"merchant_id": "MERCH-001", "period": 12345})
        self.assertEqual(res_type.status, "VALIDATION_ERROR")
        self.assertIn("must be a string", res_type.error_message)

    def test_06_state_machine_permitted_and_illegal_transitions(self):
        """Verifies the 14-state machine permits legal transitions and rejects invalid jumps."""
        # Legal transitions
        self.assertTrue(validate_state_transition(STATE_RECEIVED, STATE_UNDERSTANDING))
        self.assertTrue(validate_state_transition(STATE_UNDERSTANDING, STATE_RETRIEVING_CONTEXT))
        self.assertTrue(validate_state_transition(STATE_RETRIEVING_CONTEXT, STATE_ANALYSING))
        self.assertTrue(validate_state_transition(STATE_ANALYSING, STATE_PLANNING))
        self.assertTrue(validate_state_transition(STATE_PLANNING, STATE_READY_FOR_APPROVAL))
        self.assertTrue(validate_state_transition(STATE_READY_FOR_APPROVAL, STATE_APPROVED))
        self.assertTrue(validate_state_transition(STATE_APPROVED, STATE_EXECUTING))
        self.assertTrue(validate_state_transition(STATE_EXECUTING, STATE_VERIFYING))
        self.assertTrue(validate_state_transition(STATE_VERIFYING, STATE_COMPLETED))

        # Illegal direct transitions
        with self.assertRaises(StateTransitionError):
            validate_state_transition(STATE_RECEIVED, STATE_APPROVED)

        with self.assertRaises(StateTransitionError):
            validate_state_transition(STATE_READY_FOR_APPROVAL, STATE_COMPLETED)

        with self.assertRaises(StateTransitionError):
            validate_state_transition(STATE_COMPLETED, STATE_RECEIVED)

        # Transitioning in database
        task_id = "WF-REC-P3-SM-TEST"
        task = orchestrator.create_task_from_request("Sales dropped", task_id=task_id)
        self.assertEqual(task.current_state, STATE_READY_FOR_APPROVAL)

        # Transition to REQUIRES_HUMAN
        transition_task_state(task_id, STATE_REQUIRES_HUMAN, transitioned_by="Tester", reason="Need merchant clarification")
        history = get_task_state_history(task_id)
        self.assertGreaterEqual(len(history), 6)
        self.assertEqual(history[-1]["to_state"], STATE_REQUIRES_HUMAN)

    def test_07_epistemic_reasoning_and_unknowns(self):
        """Verifies reasoning engine categorizes confirmed data, interpretations, recommendations, and unknowns."""
        task_id = "WF-REC-P3-EPISTEMIC"
        task = orchestrator.create_task_from_request("Help bring customers back", task_id=task_id)

        epistemic = task.epistemic_report
        self.assertIsInstance(epistemic, EpistemicReportSchema)

        # 1. Confirmed Data contains verified SQLite numbers
        confirmed = " ".join(epistemic.confirmed_data)
        self.assertIn("₹112,000", confirmed)
        self.assertIn("-27.2%", confirmed)
        self.assertIn("24.0%", confirmed)
        self.assertIn("46", confirmed)
        self.assertIn("₹20,900", confirmed)

        # 2. AI Interpretation contains behavioral deduction
        interpretation = " ".join(epistemic.ai_interpretation)
        self.assertIn("do not establish why", interpretation)

        # 3. Recommendations contain the grocery offer and budget cap
        recommendations = " ".join(epistemic.recommendations)
        self.assertIn("GROCERY50", recommendations)
        self.assertIn("₹3,600", recommendations)

        # 4. Unknown Information contains explicit boundaries
        unknowns = " ".join(epistemic.unknown_information)
        self.assertIn("Competitor", unknowns)
        self.assertIn("actual reason", unknowns)

    def test_08_llm_provider_failure_and_deterministic_fallback(self):
        """Verifies offline / sandbox environment fallback to deterministic reasoning without pretending real LLM call."""
        analysis = IntentAnalyzer.analyze_request("My sales have dropped this week.")
        self.assertEqual(analysis["provider"], "DETERMINISTIC_REASONING_ENGINE")
        self.assertTrue(analysis["is_demo"])

        task = orchestrator.create_task_from_request("Sales drop help")
        self.assertTrue(task.is_demo)

    def test_09_task_persistence_and_database_recovery(self):
        """Verifies tasks persist in SQLite and can be retrieved with full schema integrity."""
        task_id = "WF-REC-P3-PERSIST-01"
        created_task = orchestrator.create_task_from_request("Sales dropped", task_id=task_id)

        loaded_task = orchestrator.get_task(task_id)
        self.assertIsNotNone(loaded_task)
        self.assertEqual(loaded_task.task_id, task_id)
        self.assertEqual(loaded_task.current_state, STATE_READY_FOR_APPROVAL)
        self.assertEqual(len(loaded_task.plan), 10)
        self.assertEqual(loaded_task.findings["recommendation"]["discount_code"], "GROCERY50")
        self.assertEqual(len(loaded_task.epistemic_report.confirmed_data), 6)

    def test_10_end_to_end_request_to_execution_and_verification(self):
        """Verifies full autonomous teammate lifecycle: Request -> Plan -> HMAC Approval -> Simulated Execution -> Closed-Loop ROI."""
        task_id = "WF-REC-P3-E2E-TEST"

        # 1. Natural Language Request -> Task Created
        task = orchestrator.create_task_from_request("My sales have dropped this week. Help me bring customers back.", task_id=task_id)
        self.assertEqual(task.current_state, STATE_READY_FOR_APPROVAL)

        # 2. Merchant Approval with HMAC Signature
        success, msg, details = orchestrator.approve_task(task_id, approved_by="Ramesh Sharma", max_budget_inr=3600.0)
        self.assertTrue(success)
        self.assertEqual(len(details["auth_signature"]), 64)
        self.assertEqual(details["current_state"], STATE_APPROVED)

        # 3. Simulated Execution & Verification
        completed_task = orchestrator.execute_simulated_action(task_id)
        self.assertEqual(completed_task.current_state, STATE_COMPLETED)

        # Step 8, 9, 10 must be completed
        step_8 = next(s for s in completed_task.plan if s.step_id == "step_8_simulate_execution")
        step_9 = next(s for s in completed_task.plan if s.step_id == "step_9_verify_execution")
        step_10 = next(s for s in completed_task.plan if s.step_id == "step_10_report_outcome")

        self.assertEqual(step_8.status, "COMPLETED")
        self.assertEqual(step_9.status, "WAITING_FOR_DATA")
        self.assertEqual(step_10.status, "COMPLETED")

        # Simulated dispatch is complete, but sales outcomes await real transactions.
        self.assertEqual(step_9.status, "WAITING_FOR_DATA")
        self.assertIsNone(step_9.execution_result["total_redeemed"])
        self.assertIsNone(step_9.execution_result["gross_recovered_sales_inr"])
        self.assertIsNone(step_9.execution_result["roi_multiple"])
        self.assertFalse(step_9.execution_result["is_verified"])

if __name__ == "__main__":
    unittest.main()
