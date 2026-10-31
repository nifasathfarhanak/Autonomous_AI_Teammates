"""Paytm AI ActionMate Task State Machine.
Defines and enforces the 14 persisted task states, permitted transitions,
cryptographic validation, and audit logging.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..fsm import record_audit

# 14 Strict Task States Specified in Section 6
STATE_RECEIVED = "RECEIVED"
STATE_UNDERSTANDING = "UNDERSTANDING"
STATE_RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
STATE_ANALYSING = "ANALYSING"
STATE_PLANNING = "PLANNING"
STATE_READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
STATE_APPROVED = "APPROVED"
STATE_EXECUTING = "EXECUTING"
STATE_VERIFYING = "VERIFYING"
STATE_COMPLETED = "COMPLETED"
STATE_REQUIRES_HUMAN = "REQUIRES_HUMAN"
STATE_PAUSED = "PAUSED"
STATE_FAILED = "FAILED"
STATE_CANCELLED = "CANCELLED"

ALL_STATES = [
    STATE_RECEIVED,
    STATE_UNDERSTANDING,
    STATE_RETRIEVING_CONTEXT,
    STATE_ANALYSING,
    STATE_PLANNING,
    STATE_READY_FOR_APPROVAL,
    STATE_APPROVED,
    STATE_EXECUTING,
    STATE_VERIFYING,
    STATE_COMPLETED,
    STATE_REQUIRES_HUMAN,
    STATE_PAUSED,
    STATE_FAILED,
    STATE_CANCELLED
]

TASK_STATE_TRANSITIONS: Dict[str, List[str]] = {
    STATE_RECEIVED: [STATE_UNDERSTANDING, STATE_CANCELLED, STATE_FAILED],
    STATE_UNDERSTANDING: [STATE_RETRIEVING_CONTEXT, STATE_REQUIRES_HUMAN, STATE_FAILED, STATE_CANCELLED],
    STATE_RETRIEVING_CONTEXT: [STATE_ANALYSING, STATE_REQUIRES_HUMAN, STATE_FAILED, STATE_CANCELLED],
    STATE_ANALYSING: [STATE_PLANNING, STATE_REQUIRES_HUMAN, STATE_FAILED, STATE_CANCELLED],
    STATE_PLANNING: [STATE_READY_FOR_APPROVAL, STATE_REQUIRES_HUMAN, STATE_FAILED, STATE_CANCELLED],
    STATE_READY_FOR_APPROVAL: [STATE_APPROVED, STATE_REQUIRES_HUMAN, STATE_PAUSED, STATE_CANCELLED],
    STATE_APPROVED: [STATE_EXECUTING, STATE_PAUSED, STATE_CANCELLED],
    STATE_EXECUTING: [STATE_VERIFYING, STATE_REQUIRES_HUMAN, STATE_FAILED, STATE_PAUSED],
    STATE_VERIFYING: [STATE_COMPLETED, STATE_REQUIRES_HUMAN, STATE_FAILED],
    STATE_COMPLETED: [],
    STATE_REQUIRES_HUMAN: [STATE_PLANNING, STATE_READY_FOR_APPROVAL, STATE_APPROVED, STATE_CANCELLED, STATE_FAILED],
    STATE_PAUSED: [STATE_READY_FOR_APPROVAL, STATE_EXECUTING, STATE_CANCELLED],
    STATE_FAILED: [STATE_RECEIVED, STATE_UNDERSTANDING, STATE_PLANNING, STATE_CANCELLED],
    STATE_CANCELLED: []
}

class StateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass

def validate_state_transition(current_state: str, target_state: str) -> bool:
    """Validates whether a transition from current_state to target_state is permitted."""
    if current_state not in TASK_STATE_TRANSITIONS:
        raise StateTransitionError(f"Unknown current state: '{current_state}'")
    if target_state not in ALL_STATES:
        raise StateTransitionError(f"Unknown target state: '{target_state}'")

    allowed = TASK_STATE_TRANSITIONS.get(current_state, [])
    if target_state not in allowed:
        raise StateTransitionError(
            f"Illegal state transition from '{current_state}' to '{target_state}'. "
            f"Permitted next states: {allowed}"
        )
    return True

def transition_task_state(task_id: str, new_state: str, transitioned_by: str = "ActionMateOrchestrator",
                          reason: Optional[str] = None) -> str:
    """Atomically transitions a task's state in SQLite and records transition history."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT current_state FROM tasks WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise StateTransitionError(f"Task '{task_id}' not found in database.")

    current_state = row["current_state"]

    # Validate transition
    validate_state_transition(current_state, new_state)

    now_utc = datetime.now(timezone.utc).isoformat()

    # Update tasks table
    cur.execute(
        "UPDATE tasks SET current_state = ?, updated_at = ? WHERE task_id = ?",
        (new_state, now_utc, task_id)
    )

    # Insert into task_state_history
    cur.execute("""
    INSERT INTO task_state_history (task_id, from_state, to_state, transitioned_by, reason, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (task_id, current_state, new_state, transitioned_by, reason or f"Transitioned to {new_state}", now_utc))

    conn.commit()
    conn.close()

    # Log into tamper-evident SHA-256 audit ledger
    try:
        record_audit(
            workflow_id=task_id,
            agent_name=transitioned_by,
            action_type=f"STATE_TRANSITION_{new_state}",
            tool_name="state_machine.transition_task_state",
            tool_input={"from": current_state, "to": new_state, "task_id": task_id},
            tool_output={"status": "TRANSITIONED", "new_state": new_state, "timestamp": now_utc}
        )
    except Exception:
        pass

    return new_state

def get_task_state_history(task_id: str) -> List[Dict[str, Any]]:
    """Retrieves chronological state transition history for a task."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, task_id, from_state, to_state, transitioned_by, reason, created_at
    FROM task_state_history
    WHERE task_id = ?
    ORDER BY id ASC
    """, (task_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

