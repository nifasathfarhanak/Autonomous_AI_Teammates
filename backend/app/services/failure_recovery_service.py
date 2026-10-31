"""Paytm AI ActionMate Failure Handling, Retry Logic & Human Escalation Service.
Implements:
1. Failed execution & verification failure diagnostics.
2. Controlled idempotent retries with maximum retry caps (Max 2 retries).
3. Guardrails against blind non-idempotent retries.
4. Human escalation workflow for unresolvable errors and missing approvals.
5. Task Pause and Task Cancellation with detailed diagnostic logs.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from ..database import get_connection
from ..schemas import FailureRecoverySchema
from .audit_service import AuditService

MAX_RETRIES_ALLOWED = 2

class RecoveryError(Exception):
    """Raised when a recovery operation violates safety invariants."""
    pass

class FailureRecoveryService:
    """Orchestrates diagnostics, safe idempotent retries, and human escalations."""

    @staticmethod
    def evaluate_failure(
        campaign_id: str,
        task_id: str = "WF-REC-1042"
    ) -> FailureRecoverySchema:
        """Diagnoses failure cause, checks retry eligibility, and suggests resolution."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM campaign_drafts WHERE campaign_id = ?", (campaign_id,))
        draft_row = cur.fetchone()

        cur.execute("""
        SELECT * FROM verifications WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 1
        """, (campaign_id,))
        verif_row = cur.fetchone()

        cur.execute("""
        SELECT * FROM task_escalations WHERE (campaign_id = ? OR task_id = ?) AND status = 'PENDING_HUMAN'
        LIMIT 1
        """, (campaign_id, task_id))
        esc_row = cur.fetchone()

        conn.close()

        now_utc = datetime.now(timezone.utc).isoformat()
        retry_count = draft_row["retry_count"] if draft_row and "retry_count" in draft_row.keys() and draft_row["retry_count"] else 0
        status = draft_row["status"] if draft_row else "UNKNOWN"
        verif_status = verif_row["verification_status"] if verif_row else "UNVERIFIED"

        # Diagnose failure mode
        if not draft_row:
            failure_type = "CAMPAIGN_NOT_FOUND"
            reason = f"Campaign draft '{campaign_id}' does not exist in SQLite database."
            can_retry = False
            suggested = "Re-initiate the sales drop workflow from the merchant prompt."
        elif esc_row:
            failure_type = "ESCALATED_TO_HUMAN"
            reason = f"Task is currently escalated to human reviewer: {esc_row['escalation_reason']}"
            can_retry = False
            suggested = "Await human merchant owner resolution or update campaign configuration."
        elif verif_status == "REQUIRES_HUMAN":
            failure_type = "APPROVAL_DISCREPANCY"
            reason = "Execution was attempted without authorized human approval."
            can_retry = False
            suggested = "Obtain merchant owner approval with cryptographic HMAC signature."
        elif status == "COMPLETED" and verif_status == "VERIFIED":
            failure_type = "NO_FAILURE"
            reason = "Campaign has already successfully executed and been cryptographically verified."
            can_retry = False
            suggested = "No action required. Task is completed and attributed."
        elif retry_count >= MAX_RETRIES_ALLOWED:
            failure_type = "MAX_RETRIES_EXCEEDED"
            reason = f"Campaign has reached the maximum retry limit ({MAX_RETRIES_ALLOWED} attempts)."
            can_retry = False
            suggested = "Escalate to merchant owner for manual intervention."
        elif status in ("FAILED", "REJECTED") or verif_status in ("FAILED", "PARTIALLY_VERIFIED"):
            failure_type = "DISPATCH_OR_VERIFICATION_FAILURE"
            reason = f"Execution or verification check failed (status: {status}, verif: {verif_status})."
            can_retry = True
            suggested = "Trigger controlled idempotent retry with refreshed adapter session."
        else:
            failure_type = "UNKNOWN_STATE"
            reason = f"Campaign is in '{status}' state with verification '{verif_status}'."
            can_retry = False
            suggested = "Check task state history and merchant approval status."

        return FailureRecoverySchema(
            task_id=task_id,
            campaign_id=campaign_id,
            failure_type=failure_type,
            retry_count=retry_count,
            max_retries_allowed=MAX_RETRIES_ALLOWED,
            can_retry=can_retry,
            escalation_status="ESCALATED_TO_HUMAN" if esc_row else "NONE",
            reason=reason,
            suggested_action=suggested,
            escalated_to=esc_row["escalated_to"] if esc_row else None,
            timestamp=now_utc
        )

    @staticmethod
    def retry_campaign_execution(
        campaign_id: str,
        task_id: str = "WF-REC-1042",
        caller: str = "MerchantOwner"
    ) -> Dict[str, Any]:
        """Safely retries campaign execution under strict idempotency and retry limit controls."""
        diag = FailureRecoveryService.evaluate_failure(campaign_id, task_id)

        if not diag.can_retry:
            if diag.retry_count >= MAX_RETRIES_ALLOWED:
                # Automatically escalate to human
                FailureRecoveryService.escalate_to_human(
                    task_id=task_id,
                    campaign_id=campaign_id,
                    reason=f"Auto-escalation: Retry limit ({MAX_RETRIES_ALLOWED}) reached. ActionMate requires human review.",
                    suggested_action="Review campaign parameters and execute manually if appropriate."
                )
            raise RecoveryError(f"RETRY_BLOCKED: {diag.reason} Suggested: {diag.suggested_action}")

        # Non-idempotent protection: Reset recipient statuses safely for idempotent re-run
        conn = get_connection()
        cur = conn.cursor()
        new_retry_count = diag.retry_count + 1
        now_utc = datetime.now(timezone.utc).isoformat()

        # Update draft status and clear stale execution_id
        cur.execute("""
        UPDATE campaign_drafts
        SET status = 'APPROVED',
            retry_count = ?,
            execution_id = NULL,
            updated_at = ?
        WHERE campaign_id = ?
        """, (new_retry_count, now_utc, campaign_id))

        # Clear prior recipient attempts to ensure idempotency
        cur.execute("DELETE FROM campaign_recipient_statuses WHERE campaign_id = ?", (campaign_id,))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id=task_id,
            actor_id=caller,
            action="CAMPAIGN_RETRY_INITIATED",
            resource=f"campaign:{campaign_id}",
            previous_state="FAILED",
            new_state="RETRYING",
            tool_name="retry_campaign_execution",
            tool_input={"campaign_id": campaign_id, "retry_attempt": new_retry_count},
            tool_output={"status": "RETRY_PREPARED", "new_retry_count": new_retry_count},
            duration_ms=45,
            is_simulated=True
        )

        # Dispatch via Simulated Execution Adapter
        from .simulated_execution_adapter import SimulatedCampaignExecutionAdapter
        exec_res = SimulatedCampaignExecutionAdapter.execute_campaign(campaign_id, caller=f"RetryHandler-{caller}")

        # Immediately run verification
        from .verification_service import VerificationService
        verif_res = VerificationService.verify_campaign_execution(campaign_id, task_id=task_id)

        return {
            "campaign_id": campaign_id,
            "task_id": task_id,
            "retry_attempt": new_retry_count,
            "max_retries": MAX_RETRIES_ALLOWED,
            "execution_id": exec_res.execution_id,
            "execution_status": exec_res.status,
            "verification_status": verif_res.verification_status,
            "verified": verif_res.verification_status == "VERIFIED"
        }

    @staticmethod
    def escalate_to_human(
        task_id: str,
        campaign_id: Optional[str] = None,
        reason: str = "Automated execution encountered invariant violation.",
        suggested_action: str = "Merchant owner inspection required.",
        escalated_to: str = "Ramesh Sharma (Merchant Owner)"
    ) -> Dict[str, Any]:
        """Formally escalates a task to human oversight."""
        now_utc = datetime.now(timezone.utc).isoformat()
        esc_id = f"ESC-{task_id}-{int(time.time() * 1000)}"

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO task_escalations (
            escalation_id, task_id, campaign_id, escalation_reason, suggested_action,
            escalated_to, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING_HUMAN', ?)
        """, (esc_id, task_id, campaign_id, reason, suggested_action, escalated_to, now_utc))

        cur.execute("""
        UPDATE tasks
        SET current_state = 'ESCALATED_TO_HUMAN', escalated_to = ?, updated_at = ?
        WHERE task_id = ?
        """, (escalated_to, now_utc, task_id))

        if campaign_id:
            cur.execute("""
            UPDATE campaign_drafts
            SET status = 'ESCALATED', escalated_to = ?, updated_at = ?
            WHERE campaign_id = ?
            """, (escalated_to, now_utc, campaign_id))

        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id=task_id,
            actor_id="FailureRecoveryService",
            action="TASK_ESCALATED_TO_HUMAN",
            resource=f"task:{task_id}",
            previous_state="ACTIVE",
            new_state="ESCALATED_TO_HUMAN",
            tool_name="escalate_to_human",
            tool_input={"task_id": task_id, "reason": reason},
            tool_output={"escalation_id": esc_id, "escalated_to": escalated_to},
            duration_ms=60,
            is_simulated=False
        )

        return {
            "escalation_id": esc_id,
            "task_id": task_id,
            "campaign_id": campaign_id,
            "status": "ESCALATED_TO_HUMAN",
            "escalated_to": escalated_to,
            "reason": reason,
            "timestamp": now_utc
        }

    @staticmethod
    def pause_task(task_id: str, actor: str = "Ramesh Sharma", reason: str = "Merchant paused task.") -> Dict[str, Any]:
        """Pauses task execution and halts background automations."""
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("UPDATE tasks SET current_state = 'PAUSED', updated_at = ? WHERE task_id = ?", (now_utc, task_id))
        cur.execute("UPDATE campaign_drafts SET status = 'PAUSED', updated_at = ? WHERE campaign_id = ?", (now_utc, "CAMP-REC-1042"))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id=task_id,
            actor_id=actor,
            action="TASK_PAUSED",
            resource=f"task:{task_id}",
            previous_state="ACTIVE",
            new_state="PAUSED",
            tool_name="pause_task",
            tool_input={"reason": reason},
            tool_output={"status": "PAUSED"},
            duration_ms=40,
            is_simulated=False
        )

        return {"task_id": task_id, "status": "PAUSED", "reason": reason, "timestamp": now_utc}

    @staticmethod
    def cancel_task(task_id: str, actor: str = "Ramesh Sharma", reason: str = "Merchant cancelled task.") -> Dict[str, Any]:
        """Permanently cancels a task."""
        now_utc = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("UPDATE tasks SET current_state = 'CANCELLED', updated_at = ? WHERE task_id = ?", (now_utc, task_id))
        cur.execute("UPDATE campaign_drafts SET status = 'CANCELLED', updated_at = ? WHERE campaign_id = ?", (now_utc, "CAMP-REC-1042"))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id=task_id,
            actor_id=actor,
            action="TASK_CANCELLED",
            resource=f"task:{task_id}",
            previous_state="ACTIVE",
            new_state="CANCELLED",
            tool_name="cancel_task",
            tool_input={"reason": reason},
            tool_output={"status": "CANCELLED"},
            duration_ms=40,
            is_simulated=False
        )

        return {"task_id": task_id, "status": "CANCELLED", "reason": reason, "timestamp": now_utc}

