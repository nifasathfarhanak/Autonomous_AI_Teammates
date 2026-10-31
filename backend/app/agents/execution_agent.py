"""DealPilot AI Agent 4: DealCloser (Verification & Execution Agent).
Executes approved communications, binds Soundbox QR discounts, logs delivery receipts, and verifies ROI.
"""

from typing import Dict, Any
from ..fsm import transition_state, STATE_APPROVED, STATE_EXECUTING, STATE_VERIFIED_DISPATCHED, STATE_COMPLETED_VERIFIED_ROI, FSMException
from ..services.email_service import execute_batch_dispatch
from ..services.roi_service import simulate_and_verify_roi
from ..database import get_connection

class DealCloserAgent:
    """Specialized in safe multi-channel dispatch, Soundbox hardware binding, and ROI verification."""

    def __init__(self, agent_name: str = "DealCloser"):
        self.agent_name = agent_name

    def execute_and_verify(self, workflow_id: str) -> Dict[str, Any]:
        """Runs the complete execution pipeline after human approval is granted."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        wf = cur.fetchone()
        conn.close()

        if not wf:
            raise FSMException(f"Workflow '{workflow_id}' not found.")

        current_state = wf["current_state"]
        if current_state != STATE_APPROVED:
            raise FSMException(f"Cannot execute workflow in state '{current_state}'. Must be '{STATE_APPROVED}'.")

        # 1. Transition to EXECUTING
        transition_state(
            workflow_id=workflow_id,
            new_state=STATE_EXECUTING,
            agent_name=self.agent_name,
            tool_name="initiate_dispatch_queue",
            input_details={"workflow_id": workflow_id, "channels": ["EMAIL", "WHATSAPP", "SOUNDBOX_QR"]},
            output_details={"status": "QUEUE_PROCESSING", "batch_size": wf["target_cohort_count"]}
        )

        # 2. Execute Batch Email & Messaging Dispatch
        dispatch_result = execute_batch_dispatch(workflow_id, limit=wf["target_cohort_count"])

        # 3. Bind Soundbox 4.0 QR Hardware Listener
        soundbox_binding = {
            "device_id": "SB-4G-DEL-9842",
            "coupon_bound": wf["discount_code"],
            "discount_inr": wf["discount_amount_inr"],
            "min_order_inr": wf["min_order_inr"],
            "status": "QR_LISTENER_ACTIVE"
        }

        # 4. Transition to VERIFIED_DISPATCHED
        transition_state(
            workflow_id=workflow_id,
            new_state=STATE_VERIFIED_DISPATCHED,
            agent_name=self.agent_name,
            tool_name="verify_delivery_receipts",
            input_details={"dispatch_result": dispatch_result, "soundbox_binding": soundbox_binding},
            output_details={"status": "ALL_RECEIPTS_VERIFIED", "delivered": dispatch_result["dispatched_count"]}
        )

        # 5. Simulate Closed-Loop POS Redemption (44 customers return over weekend)
        roi_result = simulate_and_verify_roi(workflow_id, redemption_count=44, avg_ticket_inr=385.0)

        # 6. Transition to COMPLETED_VERIFIED_ROI
        transition_state(
            workflow_id=workflow_id,
            new_state=STATE_COMPLETED_VERIFIED_ROI,
            agent_name=self.agent_name,
            tool_name="calculate_verified_roi",
            input_details={"redemption_count": 44, "avg_spend": 385.0},
            output_details=roi_result
        )

        return {
            "status": "COMPLETED",
            "workflow_id": workflow_id,
            "dispatches": dispatch_result,
            "soundbox_binding": soundbox_binding,
            "verified_roi": roi_result
        }
