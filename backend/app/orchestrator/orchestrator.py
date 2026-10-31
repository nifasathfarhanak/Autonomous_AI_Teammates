"""Paytm AI ActionMate Central Autonomous Orchestrator.
Coordinates merchant intent analysis, tool selection, context retrieval,
epistemic reasoning, multi-step planning, guarded state execution, and outcome verification.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from ..database import get_connection
from ..schemas import TaskSchema, PlanStepSchema, EpistemicReportSchema
from .state_machine import (
    STATE_RECEIVED, STATE_UNDERSTANDING, STATE_RETRIEVING_CONTEXT, STATE_ANALYSING,
    STATE_PLANNING, STATE_READY_FOR_APPROVAL, STATE_APPROVED, STATE_EXECUTING,
    STATE_VERIFYING, STATE_COMPLETED, STATE_REQUIRES_HUMAN, STATE_FAILED,
    transition_task_state, validate_state_transition
)
from .tool_registry import registry
from .intent_analyzer import IntentAnalyzer
from .reasoning_engine import ReasoningEngine
from .planner import TaskPlanner
from ..fsm import generate_approval_signature, record_audit

class ActionMateOrchestrator:
    """Central agent orchestrator for Paytm AI ActionMate."""

    def __init__(self):
        self.tool_registry = registry

    def create_task_from_request(
        self,
        user_request: str,
        merchant_id: str = "MERCH-001",
        task_id: Optional[str] = None
    ) -> TaskSchema:
        """Executes the full understanding, context retrieval, reasoning, and planning pipeline.
        Advances state through: RECEIVED -> UNDERSTANDING -> RETRIEVING_CONTEXT -> ANALYSING -> PLANNING -> READY_FOR_APPROVAL.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        t_id = task_id or f"WF-REC-{datetime.now(timezone.utc).strftime('%H%M%S')}"

        # 1. State: RECEIVED
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO tasks (
            task_id, merchant_id, original_request, detected_intent, current_state,
            risk_classification, requires_approval, entities_json, required_data_json,
            plan_json, findings_json, epistemic_report_json, recommendations_json,
            approval_details_json, execution_result_json, is_demo, created_at, updated_at
        ) VALUES (
            ?, ?, ?, 'PENDING_ANALYSIS', ?, 'LOW', 1, '{}', '[]', '[]', '{}', '{}', '{}', '{}', '{}', 1, ?, ?
        )
        """, (t_id, merchant_id, user_request, STATE_RECEIVED, now_utc, now_utc))
        conn.commit()
        conn.close()

        # 2. State: UNDERSTANDING
        transition_task_state(t_id, STATE_UNDERSTANDING, transitioned_by="ActionMateOrchestrator", reason="Parsing intent and entity extraction")
        intent_analysis = IntentAnalyzer.analyze_request(user_request, merchant_id)

        # 3. State: RETRIEVING_CONTEXT (invoking registered backend tools)
        transition_task_state(t_id, STATE_RETRIEVING_CONTEXT, transitioned_by="ActionMateOrchestrator", reason="Retrieving sales and customer metrics from tool registry")

        res_sales = self.tool_registry.execute("get_sales_summary", {"merchant_id": merchant_id})
        res_drop = self.tool_registry.execute("compare_sales_periods", {"merchant_id": merchant_id})
        res_repeat = self.tool_registry.execute("get_repeat_purchase_trend", {"merchant_id": merchant_id})
        res_segs = self.tool_registry.execute("get_customer_segments", {"merchant_id": merchant_id})
        res_prods = self.tool_registry.execute("get_product_performance", {"merchant_id": merchant_id})
        res_profile = self.tool_registry.execute("get_merchant_profile", {"merchant_id": merchant_id})

        sales_drop = res_drop.data if res_drop.status == "SUCCESS" else {}
        repeat_analysis = res_repeat.data if res_repeat.status == "SUCCESS" else {}
        merchant_profile = res_profile.data if res_profile.status == "SUCCESS" else {}
        customer_segments = res_segs.data if res_segs.status == "SUCCESS" else []
        product_performance = res_prods.data if res_prods.status == "SUCCESS" else []

        # 4. State: ANALYSING (epistemic reasoning & synthesis)
        transition_task_state(t_id, STATE_ANALYSING, transitioned_by="ActionMateOrchestrator", reason="Synthesizing confirmed facts and identifying customers with no recent receipts")
        findings = ReasoningEngine.evaluate(
            sales_drop=sales_drop,
            repeat_analysis=repeat_analysis,
            merchant_profile=merchant_profile,
            customer_segments=customer_segments,
            product_performance=product_performance,
            sales_summary=res_sales.data if res_sales.status == "SUCCESS" else {}
        )

        # 5. State: PLANNING (generating structured 10-step plan)
        transition_task_state(t_id, STATE_PLANNING, transitioned_by="ActionMateOrchestrator", reason="Formulating the action plan and binding parameters to merchant records")
        plan_steps = TaskPlanner.generate_plan(
            merchant_id=merchant_id,
            target_cohort_size=findings.get("target_cohort_size", 240),
            discount_code=findings["recommendation"]["discount_code"],
            discount_amount_inr=findings["recommendation"]["discount_amount_inr"],
            min_order_inr=findings["recommendation"]["min_order_inr"],
            cap_inr=findings["recommendation"]["max_liability_cap_inr"],
            is_approved=False,
            is_executed=False,
            is_completed=False
        )

        # 6. State: READY_FOR_APPROVAL
        transition_task_state(t_id, STATE_READY_FOR_APPROVAL, transitioned_by="ActionMateOrchestrator", reason="Awaiting merchant sign-off for financial liability cap")

        epistemic_report_schema = EpistemicReportSchema(**findings["epistemic_report"])

        task = TaskSchema(
            task_id=t_id,
            merchant_id=merchant_id,
            original_request=user_request,
            detected_intent=intent_analysis["detected_intent"],
            relevant_entities=intent_analysis["relevant_entities"],
            required_data=intent_analysis["required_data"],
            risk_classification=intent_analysis["risk_classification"],
            approval_requirements=intent_analysis["approval_requirements"],
            current_state=STATE_READY_FOR_APPROVAL,
            plan=plan_steps,
            findings=findings,
            epistemic_report=epistemic_report_schema,
            is_demo=True,
            created_at=now_utc,
            updated_at=datetime.now(timezone.utc).isoformat()
        )

        # Persist full task details to SQLite
        self._save_task_record(task)

        # Maintain backward compatibility with legacy workflows table
        self._sync_legacy_workflow(task)

        return task

    def get_task(self, task_id: str) -> Optional[TaskSchema]:
        """Retrieves a persisted task by ID."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            # Fallback check on legacy WF-REC-1042
            if task_id == "WF-REC-1042":
                return self.create_task_from_request(
                    user_request="My sales have dropped this week. Help me bring customers back.",
                    merchant_id="MERCH-001",
                    task_id="WF-REC-1042"
                )
            return None

        data = dict(row)
        plan_steps = [PlanStepSchema(**step) for step in json.loads(data.get("plan_json") or "[]")]
        epistemic = EpistemicReportSchema(**json.loads(data.get("epistemic_report_json") or "{}"))

        return TaskSchema(
            task_id=data["task_id"],
            merchant_id=data["merchant_id"],
            original_request=data["original_request"],
            detected_intent=data["detected_intent"],
            relevant_entities=json.loads(data.get("entities_json") or "{}"),
            required_data=json.loads(data.get("required_data_json") or "[]"),
            risk_classification=data["risk_classification"],
            approval_requirements=json.loads(data.get("approval_details_json") or "{}"),
            current_state=data["current_state"],
            plan=plan_steps,
            findings=json.loads(data.get("findings_json") or "{}"),
            epistemic_report=epistemic,
            is_demo=bool(data["is_demo"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )

    def list_tasks(self, merchant_id: str = "MERCH-001") -> List[TaskSchema]:
        """Lists all tasks for a merchant ordered by creation date."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT task_id FROM tasks WHERE merchant_id = ? ORDER BY created_at DESC", (merchant_id,))
        rows = cur.fetchall()
        conn.close()

        tasks = []
        for r in rows:
            t = self.get_task(r["task_id"])
            if t:
                tasks.append(t)
        return tasks

    def approve_task(
        self,
        task_id: str,
        approved_by: str = "Ramesh Sharma",
        max_budget_inr: float = 3600.0,
        message_override: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validates approval preconditions, generates HMAC signature, and advances state to APPROVED."""
        task = self.get_task(task_id)
        if not task:
            return False, f"Task '{task_id}' not found.", {}

        # Idempotent check
        signature = generate_approval_signature(task_id, task.merchant_id, max_budget_inr)
        if task.current_state == STATE_APPROVED:
            return True, "Task is already approved.", {
                "auth_signature": signature,
                "current_state": STATE_APPROVED
            }

        if task.current_state not in (STATE_READY_FOR_APPROVAL, STATE_REQUIRES_HUMAN):
            return False, f"Task is in state '{task.current_state}', cannot approve.", {}

        hard_cap = task.approval_requirements.get("max_authorized_budget_inr", 3600.0)
        ceiling = task.approval_requirements.get("liability_ceiling_inr", hard_cap * 1.5)
        if max_budget_inr > ceiling:
            return False, f"Authorized budget (₹{max_budget_inr}) exceeds liability ceiling (₹{ceiling}).", {}

        # Generate cryptographic HMAC-SHA256 signature
        signature = generate_approval_signature(task_id, task.merchant_id, max_budget_inr)
        approval_id = f"APPR-TSK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        # Transition task state to APPROVED
        transition_task_state(task_id, STATE_APPROVED, transitioned_by=approved_by, reason="Merchant authorized financial discount budget")

        # Update approvals table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO approvals (id, workflow_id, decision, approved_by, max_budget_authorized_inr,
                              message_override, auth_signature)
        VALUES (?, ?, 'APPROVED', ?, ?, ?, ?)
        """, (approval_id, task_id, approved_by, max_budget_inr, message_override, signature))
        conn.commit()
        conn.close()

        # Update in-memory plan status
        for s in task.plan:
            if s.step_id == "step_7_request_approval":
                s.status = "COMPLETED"
                s.execution_result = {"status": "APPROVED", "signature": signature, "approved_by": approved_by}
            elif s.step_id == "step_8_simulate_execution":
                s.status = "READY_FOR_EXECUTION"

        task.current_state = STATE_APPROVED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_task_record(task)
        self._sync_legacy_workflow(task, signature=signature, approved_by=approved_by)

        return True, "Task successfully approved with cryptographic signature.", {
            "approval_id": approval_id,
            "auth_signature": signature,
            "max_budget_authorized_inr": max_budget_inr,
            "current_state": STATE_APPROVED
        }

    def execute_simulated_action(self, task_id: str) -> TaskSchema:
        """Transitions APPROVED -> EXECUTING -> VERIFYING -> COMPLETED.
        Dispatches simulated messages and verifies closed-loop ROI.
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        if task.current_state != STATE_APPROVED:
            raise ValueError(f"Task is in state '{task.current_state}', must be 'APPROVED' to execute.")

        # 1. State: EXECUTING
        transition_task_state(task_id, STATE_EXECUTING, transitioned_by="ActionMateOrchestrator", reason="Dispatching simulated outreach")
        dispatch_res = self.tool_registry.execute("execute_simulated_dispatch", {"campaign_code": "RET50", "target_count": 240})

        for s in task.plan:
            if s.step_id == "step_8_simulate_execution":
                s.status = "COMPLETED"
                s.execution_result = dispatch_res.data
            elif s.step_id == "step_9_verify_execution":
                s.status = "READY_FOR_EXECUTION"

        # 2. State: VERIFYING
        transition_task_state(task_id, STATE_VERIFYING, transitioned_by="ActionMateOrchestrator", reason="Verifying redemption telemetry at Soundbox QR")
        verify_res = self.tool_registry.execute("verify_pos_outcomes", {"campaign_code": "RET50"})

        for s in task.plan:
            if s.step_id == "step_9_verify_execution":
                s.status = "COMPLETED"
                s.execution_result = verify_res.data
            elif s.step_id == "step_10_report_outcome":
                s.status = "COMPLETED"
                s.execution_result = {
                    "status": "COMPLETED",
                    "roi_multiple": verify_res.data.get("roi_multiple", 6.38),
                    "gross_recovered_sales_inr": verify_res.data.get("gross_recovered_sales_inr", 16940.0)
                }

        # 3. State: COMPLETED
        transition_task_state(task_id, STATE_COMPLETED, transitioned_by="ActionMateOrchestrator", reason="Verified closed-loop ROI accounting completed")

        task.current_state = STATE_COMPLETED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_task_record(task)

        # Update legacy roi_metrics table
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO roi_metrics (
            workflow_id, total_targeted, total_delivered, total_redeemed,
            gross_recovered_sales_inr, total_discounts_paid_inr, total_execution_cost_inr,
            net_recovered_profit_inr, roi_multiple, is_verified, last_updated_at
        ) VALUES (?, 240, 232, 44, 16940.0, 2200.0, 96.0, 14644.0, 6.38, 1, ?)
        """, (task_id, datetime.now(timezone.utc).isoformat()))

        cur.execute("UPDATE workflows SET current_state = 'COMPLETED_VERIFIED_ROI', updated_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), task_id))
        conn.commit()
        conn.close()

        return task

    def _save_task_record(self, task: TaskSchema):
        """Persists task state and structured fields into the SQLite tasks table."""
        conn = get_connection()
        cur = conn.cursor()
        plan_dicts = [s.dict() for s in task.plan]
        cur.execute("""
        INSERT OR REPLACE INTO tasks (
            task_id, merchant_id, original_request, detected_intent, current_state,
            risk_classification, requires_approval, entities_json, required_data_json,
            plan_json, findings_json, epistemic_report_json, recommendations_json,
            approval_details_json, execution_result_json, is_demo, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            task.task_id,
            task.merchant_id,
            task.original_request,
            task.detected_intent,
            task.current_state,
            task.risk_classification,
            1 if task.approval_requirements.get("requires_merchant_approval", True) else 0,
            json.dumps(task.relevant_entities),
            json.dumps(task.required_data),
            json.dumps(plan_dicts),
            json.dumps(task.findings),
            json.dumps(task.epistemic_report.dict()),
            json.dumps(task.findings.get("recommendation", {})),
            json.dumps(task.approval_requirements),
            json.dumps({}),
            1 if task.is_demo else 0,
            task.created_at,
            task.updated_at
        ))
        conn.commit()
        conn.close()

    def _sync_legacy_workflow(self, task: TaskSchema, signature: str = None, approved_by: str = None):
        """Syncs task record to legacy workflows table to preserve full backward compatibility."""
        conn = get_connection()
        cur = conn.cursor()

        messages_payload = {
            "en": "Hi [Customer Name]! We miss you at Sharma Supplies. Enjoy ₹50 OFF on your next order above ₹249 this weekend with code RET50 on Paytm Soundbox / QR. Valid till Sunday midnight!",
            "hi": "नमस्ते [ग्राहक का नाम]! शर्मा सप्लाइज में आपकी कमी महसूस हुई। इस वीकेंड पेटीएम QR पर कोड RET50 के साथ ₹249 से ऊपर के ऑर्डर पर ₹50 की छूट पाएं। रविवार मध्यरात्रि तक वैध!"
        }

        legacy_state = "AWAITING_APPROVAL"
        if task.current_state == STATE_APPROVED:
            legacy_state = "APPROVED"
        elif task.current_state == STATE_EXECUTING:
            legacy_state = "EXECUTING"
        elif task.current_state in (STATE_VERIFYING, STATE_COMPLETED):
            legacy_state = "COMPLETED_VERIFIED_ROI"

        cur.execute("""
        INSERT OR REPLACE INTO workflows (
            id, merchant_id, title, workflow_type, current_state,
            detected_leakage_inr, target_cohort_count, discount_code,
            discount_amount_inr, min_order_inr, max_liability_cap_inr,
            anomaly_payload, strategy_payload, messages_payload,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, 'REVENUE_RECOVERY', ?,
            20900.0, 240, 'RET50', 50.0, 249.0, 3600.0,
            ?, ?, ?, ?, ?
        )
        """, (
            task.task_id,
            task.merchant_id,
            "Recover 240 Dormant Repeat Diners",
            legacy_state,
            json.dumps(task.findings),
            json.dumps(task.findings.get("recommendation", {})),
            json.dumps(messages_payload),
            task.created_at or datetime.now(timezone.utc).isoformat(),
            task.updated_at or datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

# Global orchestrator singleton
orchestrator = ActionMateOrchestrator()
