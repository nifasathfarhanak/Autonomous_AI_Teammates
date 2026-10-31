"""DealPilot AI Persistent Finite State Machine (FSM).
Enforces guarded transitions, cryptographic HMAC approvals, and SHA-256 audit chaining.
"""

import json
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from .database import get_connection
from .config import SECRET_KEY

# Strict FSM State Definitions
STATE_DETECTED = "DETECTED"
STATE_COHORT_IDENTIFIED = "COHORT_IDENTIFIED"
STATE_STRATEGY_FORMULATED = "STRATEGY_FORMULATED"
STATE_COPY_DRAFTED = "COPY_DRAFTED"
STATE_AWAITING_APPROVAL = "AWAITING_APPROVAL"
STATE_APPROVED = "APPROVED"
STATE_REJECTED = "REJECTED"
STATE_EXECUTING = "EXECUTING"
STATE_VERIFIED_DISPATCHED = "VERIFIED_DISPATCHED"
STATE_COMPLETED_VERIFIED_ROI = "COMPLETED_VERIFIED_ROI"

ALLOWED_TRANSITIONS = {
    STATE_DETECTED: [STATE_COHORT_IDENTIFIED],
    STATE_COHORT_IDENTIFIED: [STATE_STRATEGY_FORMULATED],
    STATE_STRATEGY_FORMULATED: [STATE_COPY_DRAFTED],
    STATE_COPY_DRAFTED: [STATE_AWAITING_APPROVAL],
    STATE_AWAITING_APPROVAL: [STATE_APPROVED, STATE_REJECTED],
    STATE_APPROVED: [STATE_EXECUTING],
    STATE_EXECUTING: [STATE_VERIFIED_DISPATCHED],
    STATE_VERIFIED_DISPATCHED: [STATE_COMPLETED_VERIFIED_ROI],
    STATE_REJECTED: [],
    STATE_COMPLETED_VERIFIED_ROI: []
}

class FSMException(Exception):
    """Raised when an illegal FSM transition is attempted."""
    pass

def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full workflow record with parsed JSON payloads."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["anomaly_payload"] = json.loads(data["anomaly_payload"])
    data["strategy_payload"] = json.loads(data["strategy_payload"])
    data["messages_payload"] = json.loads(data["messages_payload"])
    return data

def record_audit(workflow_id: str, agent_name: str, action_type: str, tool_name: str,
                 tool_input: Dict[str, Any], tool_output: Dict[str, Any], duration_ms: int = 150) -> str:
    """Appends an immutable SHA-256 chained entry into audit_trail."""
    conn = get_connection()
    cur = conn.cursor()

    # Fetch last hash in global chain
    cur.execute("SELECT current_hash FROM audit_trail ORDER BY id DESC LIMIT 1")
    last_row = cur.fetchone()
    prev_hash = last_row["current_hash"] if last_row else "GENESIS_BLOCK_0000000000000000000000000000000000000000000000000000000000000000"

    from .services.audit_service import AuditService
    inp_obj = tool_input or {}
    out_obj = tool_output or {}
    now_utc = datetime.now(timezone.utc).isoformat()
    cur_hash = AuditService.calculate_payload_hash(
        prev_hash=prev_hash,
        agent_name=agent_name,
        action_type=action_type,
        tool_name=tool_name,
        tool_input=inp_obj,
        tool_output=out_obj,
        timestamp_utc=now_utc
    )

    cur.execute("""
    INSERT INTO audit_trail (workflow_id, agent_name, actor_id, action_type, tool_name,
                            tool_input_json, tool_output_json, execution_duration_ms,
                            previous_hash, current_hash, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (workflow_id, agent_name, agent_name, action_type, tool_name,
          json.dumps(inp_obj, sort_keys=True), json.dumps(out_obj, sort_keys=True), duration_ms, prev_hash, cur_hash, now_utc))
    conn.commit()
    conn.close()
    return cur_hash

def transition_state(workflow_id: str, new_state: str, agent_name: str, tool_name: str,
                     input_details: Dict[str, Any], output_details: Dict[str, Any]) -> str:
    """Safely transitions a workflow to a new state and logs audit trail."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_state FROM workflows WHERE id = ?", (workflow_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise FSMException(f"Workflow '{workflow_id}' not found.")

    current_state = row["current_state"]
    allowed = ALLOWED_TRANSITIONS.get(current_state, [])
    if new_state not in allowed:
        conn.close()
        raise FSMException(f"Illegal FSM transition from '{current_state}' to '{new_state}'. Allowed: {allowed}")

    now_utc = datetime.now(timezone.utc).isoformat()
    cur.execute("UPDATE workflows SET current_state = ?, updated_at = ? WHERE id = ?",
                (new_state, now_utc, workflow_id))
    conn.commit()
    conn.close()

    # Record in audit trail
    record_audit(workflow_id, agent_name, f"STATE_CHANGE_TO_{new_state}", tool_name, input_details, output_details)
    return new_state

def generate_approval_signature(workflow_id: str, merchant_id: str, max_budget: float) -> str:
    """Generates a cryptographic HMAC-SHA256 signature for authorized approval."""
    payload = f"{workflow_id}:{merchant_id}:{max_budget:.2f}"
    return hmac.new(SECRET_KEY.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()

def approve_workflow(workflow_id: str, approved_by: str, max_budget_authorized: float,
                     message_override: Optional[str] = None) -> Tuple[bool, str]:
    """Applies human authorization signature and transitions workflow from AWAITING_APPROVAL to APPROVED."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT merchant_id, current_state, max_liability_cap_inr FROM workflows WHERE id = ?", (workflow_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Workflow not found."

    if row["current_state"] != STATE_AWAITING_APPROVAL:
        conn.close()
        return False, f"Workflow is in '{row['current_state']}', cannot approve."

    merchant_id = row["merchant_id"]
    hard_cap = row["max_liability_cap_inr"]

    # Enforce liability bounds
    if max_budget_authorized > hard_cap * 1.5:
        conn.close()
        return False, f"Authorized budget (₹{max_budget_authorized}) exceeds maximum safety ceiling (₹{hard_cap * 1.5})."

    # Generate cryptographic signature
    signature = generate_approval_signature(workflow_id, merchant_id, max_budget_authorized)
    approval_id = f"APPR-WF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

    cur.execute("""
    INSERT OR REPLACE INTO approvals (id, workflow_id, decision, approved_by, max_budget_authorized_inr,
                          message_override, auth_signature)
    VALUES (?, ?, 'APPROVED', ?, ?, ?, ?)
    """, (approval_id, workflow_id, approved_by, max_budget_authorized, message_override, signature))

    # If message override provided, update messages_payload
    if message_override:
        cur.execute("SELECT messages_payload FROM workflows WHERE id = ?", (workflow_id,))
        msgs = json.loads(cur.fetchone()["messages_payload"])
        msgs["en"] = message_override
        cur.execute("UPDATE workflows SET messages_payload = ? WHERE id = ?", (json.dumps(msgs), workflow_id))

    conn.commit()
    conn.close()

    # Perform transition
    transition_state(
        workflow_id=workflow_id,
        new_state=STATE_APPROVED,
        agent_name="HumanOperator",
        tool_name="merchant_sign_off",
        input_details={"approved_by": approved_by, "budget": max_budget_authorized, "has_override": bool(message_override)},
        output_details={"approval_id": approval_id, "signature": signature, "status": "APPROVED"}
    )
    return True, signature

def reject_workflow(workflow_id: str, rejected_by: str, reason: str) -> bool:
    """Rejects workflow and archives state."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT current_state FROM workflows WHERE id = ?", (workflow_id,))
    row = cur.fetchone()
    if not row or row["current_state"] != STATE_AWAITING_APPROVAL:
        conn.close()
        return False

    approval_id = f"REJ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    cur.execute("""
    INSERT INTO approvals (id, workflow_id, decision, approved_by, max_budget_authorized_inr,
                          message_override, auth_signature)
    VALUES (?, ?, 'REJECTED', ?, 0.0, ?, 'REJECTED_BY_MERCHANT')
    """, (approval_id, workflow_id, rejected_by, reason))
    conn.commit()
    conn.close()

    transition_state(
        workflow_id=workflow_id,
        new_state=STATE_REJECTED,
        agent_name="HumanOperator",
        tool_name="merchant_reject",
        input_details={"rejected_by": rejected_by, "reason": reason},
        output_details={"status": "REJECTED_AND_ARCHIVED"}
    )
    return True

def reset_to_initial_state(workflow_id: str):
    """Resets workflow back to AWAITING_APPROVAL for interactive demo testing."""
    conn = get_connection()
    cur = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()
    cur.execute("UPDATE workflows SET current_state = 'AWAITING_APPROVAL', updated_at = ? WHERE id = ?", (now_utc, workflow_id))
    try:
        cur.execute("UPDATE tasks SET current_state = 'READY_FOR_APPROVAL', updated_at = ? WHERE task_id = ?", (now_utc, workflow_id))
    except Exception:
        pass
    try:
        cur.execute("DELETE FROM dispatches WHERE workflow_id = ?", (workflow_id,))
    except Exception:
        pass
    cur.execute("DELETE FROM approvals WHERE workflow_id = ?", (workflow_id,))
    cur.execute("""
    UPDATE roi_metrics SET total_delivered = 0, total_redeemed = 0,
                           gross_recovered_sales_inr = 0.0, total_discounts_paid_inr = 0.0,
                           net_recovered_profit_inr = 0.0, roi_multiple = 0.0, is_verified = 0
    WHERE workflow_id = ?
    """, (workflow_id,))
    conn.commit()
    conn.close()
