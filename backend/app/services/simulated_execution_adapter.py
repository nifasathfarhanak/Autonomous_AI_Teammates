"""Paytm AI ActionMate Simulated Campaign Execution Adapter.
Simulates multi-channel customer outreach (SMS, WhatsApp, Soundbox audio banner)
without connecting to real Paytm production systems or executing real customer dispatches.
Enforces recipient validation, DND suppression, idempotency, per-customer status logging,
and cryptographic audit ledger chaining.
"""

import time
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..schemas import SimulatedExecutionResultSchema
from .campaign_service import CampaignService, DND_PREFIXES
from ..fsm import record_audit

class ExecutionAdapterError(Exception):
    """Raised when simulated execution validation fails."""
    pass

class DuplicateExecutionError(ExecutionAdapterError):
    """Raised when an attempt is made to re-execute an already completed campaign."""
    pass

class SimulatedCampaignExecutionAdapter:
    """Modular execution adapter for simulated campaign dispatches."""

    @staticmethod
    def execute_campaign(
        campaign_id: str,
        caller: str = "Ramesh Sharma (Merchant Owner)",
        idempotency_key: Optional[str] = None
    ) -> SimulatedExecutionResultSchema:
        """Executes a simulated multi-channel dispatch for an approved campaign draft."""
        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            raise ExecutionAdapterError(f"Campaign '{campaign_id}' not found.")

        # Strict Backend Precondition Enforcement (Phase 5)
        from .governance_service import GovernanceService, ApprovalPreconditionError, ContentDriftError
        try:
            GovernanceService.verify_execution_preconditions(campaign_id, caller)
        except DuplicateExecutionError:
            raise
        except (ApprovalPreconditionError, ContentDriftError) as pe:
            if "Idempotency" in str(pe) or "already been executed" in str(pe):
                raise DuplicateExecutionError(str(pe))
            raise ExecutionAdapterError(str(pe))

        # 3. Audience Evaluation & Recipient Validation
        audience = CampaignService.evaluate_campaign_audience(
            merchant_id=draft.merchant_id,
            segment_key=draft.target_customer_segment
        )

        if audience.eligible_count == 0:
            CampaignService.log_campaign_activity(
                campaign_id=campaign_id,
                event_type="EXECUTION_FAILED_EMPTY_AUDIENCE",
                description="Simulated execution aborted: Zero eligible recipients found.",
                actor=caller,
                details={"total_evaluated": audience.total_evaluated, "excluded_count": audience.excluded_count}
            )
            raise ExecutionAdapterError(
                f"Simulated execution aborted: Audience contains 0 eligible customers. "
                f"All {audience.total_evaluated} evaluated candidates were excluded."
            )

        # 4. Generate Unique Execution ID
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        exec_id = f"EXEC-{campaign_id}-{timestamp_str}"
        now_utc = datetime.now(timezone.utc).isoformat()

        # 5. Simulate Per-Customer Dispatch & Channel Delivery
        channels = ["WHATSAPP", "SMS", "SOUNDBOX_BANNER"]
        recipient_statuses = []
        delivered_count = 0
        dnd_suppressed_count = 0
        failed_count = 0

        conn = get_connection()
        cur = conn.cursor()

        for idx, cust in enumerate(audience.eligible_customers):
            cid = cust.get("customer_id", f"CUST-SIM-{idx}")
            cname = cust.get("customer_name", "Valued Customer")
            phone = cust.get("phone", "")
            email = cust.get("email", "")

            # Personalize message for this recipient
            msg = CampaignService.render_personalized_message(
                customer_data=cust,
                merchant_name="Sharma Commercial & Industrial Supplies",
                offer_details=draft.offer_details if draft.offer_configured else None
            )

            # Check DND suppression
            is_dnd = any(phone.startswith(prefix) for prefix in DND_PREFIXES)

            if is_dnd:
                sim_status = "DND_SUPPRESSED"
                exclusion_reason = "NATIONAL_DND_REGISTRY_SUPPRESSION"
                dnd_suppressed_count += 1
            else:
                sim_status = "DELIVERED"
                exclusion_reason = None
                delivered_count += 1

            recipient_record = {
                "execution_id": exec_id,
                "customer_id": cid,
                "customer_name": cname,
                "channel": "WHATSAPP_SMS_MULTI",
                "contact_destination": phone or email,
                "message_preview": msg.body_en[:80] + "...",
                "status": sim_status,
                "exclusion_reason": exclusion_reason,
                "simulated_timestamp": now_utc,
                "is_demo": True
            }
            recipient_statuses.append(recipient_record)

            # Record in SQLite campaign_recipient_statuses table
            cur.execute("""
            INSERT INTO campaign_recipient_statuses (
                campaign_id, execution_id, customer_id, customer_name,
                channel, contact_destination, message_rendered, simulated_status,
                exclusion_reason, simulated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign_id, exec_id, cid, cname,
                "WHATSAPP_SMS_MULTI", phone or email, msg.body_en, sim_status,
                exclusion_reason, now_utc
            ))

        # Also log excluded candidate customers for full audit transparency
        for exc in audience.excluded_customers:
            cur.execute("""
            INSERT INTO campaign_recipient_statuses (
                campaign_id, execution_id, customer_id, customer_name,
                channel, contact_destination, message_rendered, simulated_status,
                exclusion_reason, simulated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'EXCLUDED', ?, ?)
            """, (
                campaign_id, exec_id, exc["customer_id"], exc["customer_name"],
                "EXCLUDED_PRE_DISPATCH", exc.get("phone") or exc.get("email", ""),
                "[MESSAGE_SUPPRESSED_PRE_DISPATCH]", exc["reason"], now_utc
            ))

        # 6. Update Campaign Draft Status to COMPLETED
        exec_summary = {
            "execution_id": exec_id,
            "status": "COMPLETED",
            "total_attempted": audience.eligible_count,
            "delivered_count": delivered_count,
            "dnd_suppressed_count": dnd_suppressed_count,
            "failed_count": failed_count,
            "channels": channels,
            "executed_at": now_utc,
            "adapter": "SimulatedCampaignExecutionAdapter (DEMO)",
            "is_demo": True
        }

        cur.execute("""
        UPDATE campaign_drafts
        SET status = 'COMPLETED', execution_id = ?, execution_result_json = ?,
            idempotency_key = ?, updated_at = ?
        WHERE campaign_id = ?
        """, (exec_id, json.dumps(exec_summary), idempotency_key or exec_id, now_utc, campaign_id))

        # 7. Log Activity Timeline
        cur.execute("""
        INSERT INTO campaign_activity_timeline (campaign_id, event_type, description, actor, details_json, created_at)
        VALUES (?, 'SIMULATED_CAMPAIGN_EXECUTED', ?, ?, ?, ?)
        """, (
            campaign_id,
            f"Simulated dispatch of {audience.eligible_count} messages ({delivered_count} delivered, {dnd_suppressed_count} DND suppressed)",
            caller,
            json.dumps(exec_summary),
            now_utc
        ))

        # 8. Record in Legacy Executions Table for full system coherence if strategy exists
        try:
            cur.execute("SELECT strategy_id FROM recovery_strategies LIMIT 1")
            existing_strat = cur.fetchone()
            legacy_strat_id = existing_strat["strategy_id"] if existing_strat else None
            if legacy_strat_id:
                for s in recipient_statuses[:10]:
                    cur.execute("""
                    INSERT OR REPLACE INTO executions (
                        execution_id, strategy_id, customer_id, channel, recipient_email,
                        sent_subject, sent_body, dispatch_status, delivery_timestamp, response_classification
                    ) VALUES (?, ?, ?, 'WHATSAPP_SMS', ?, ?, ?, ?, ?, 'NO_RESPONSE')
                    """, (
                        f"{exec_id}-{s['customer_id']}", legacy_strat_id, s["customer_id"],
                        s["contact_destination"], draft.messages.get("en", "Special Offer")[:50],
                        s["message_preview"], s["status"], now_utc
                    ))
        except Exception:
            pass

        conn.commit()
        conn.close()

        # 9. Audit Ledger Chaining
        try:
            from .audit_service import AuditService
            AuditService.log_audit_event(
                merchant_id="MERCH-001",
                task_id="WF-REC-1042",
                actor_id="SimulatedCampaignExecutionAdapter",
                action="SIMULATED_CAMPAIGN_DISPATCH",
                resource=f"campaign:{campaign_id}",
                previous_state="APPROVED",
                new_state="COMPLETED",
                tool_name="execute_demo_campaign",
                tool_input={"campaign_id": campaign_id, "audience_size": audience.eligible_count},
                tool_output=exec_summary,
                duration_ms=220,
                is_simulated=True
            )
        except Exception:
            pass

        return SimulatedExecutionResultSchema(
            execution_id=exec_id,
            campaign_id=campaign_id,
            status="COMPLETED",
            total_attempted=audience.eligible_count,
            delivered_count=delivered_count,
            dnd_suppressed_count=dnd_suppressed_count,
            failed_count=failed_count,
            channels=channels,
            executed_at=now_utc,
            recipient_statuses=recipient_statuses,
            is_demo=True
        )
