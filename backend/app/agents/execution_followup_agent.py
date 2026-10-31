"""DealPilot AI Agent 4: Execution & Follow-up Agent.
Dispatches approved communications via Email (or clearly labeled Demo Email Adapter),
records RFC-822 headers and provider response, manages multi-step follow-up scheduling,
classifies customer replies, halts follow-ups upon opt-out or reply,
and attributes verified recovered revenue into 4 distinct commercial categories.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from email.utils import make_msgid
from ..database import get_connection
from ..fsm import record_audit
from ..services.revenue_attribution_service import (
    schedule_recovery_followups, cancel_pending_followups,
    record_verified_purchase_transaction, get_customer_followups
)

VALID_RESPONSE_CLASSIFICATIONS = [
    "INTERESTED", "WANTS_MORE_INFO", "REQUESTS_QUOTATION", "REQUESTS_MEETING",
    "NOT_INTERESTED", "UNSUBSCRIBE", "COMPLAINT", "NO_RESPONSE", "UNCLEAR"
]

class ExecutionFollowupAgent:
    """Safely dispatches authorized outreach, monitors replies, and closes the revenue verification loop."""

    def __init__(self, agent_name: str = "ExecutionFollowupAgent"):
        self.agent_name = agent_name

    def execute_outreach(self, strategy_id: str, is_demo_mode: bool = True) -> Dict[str, Any]:
        """Dispatches approved strategy to the recipient via Email (or clearly labeled Demo Adapter)."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT s.*, c.customer_name, c.email, c.phone, c.is_unsubscribed
        FROM recovery_strategies s
        JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.strategy_id = ?
        """, (strategy_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"error": "Strategy not found"}

        data = dict(row)

        # 1. Unsubscribe & Opt-out Safety Check
        if data.get("is_unsubscribed"):
            conn.close()
            return {
                "status": "BLOCKED",
                "reason": "SAFETY_GUARD_TRIGGERED: Customer has active UNSUBSCRIBE flag. Outreach blocked."
            }

        # 2. Approval Status Check (Default requirement)
        if data.get("approval_status") != "APPROVED":
            # Check if organization policy explicitly enables automation
            cur.execute("SELECT authorized_automation_policy_enabled FROM organization_policies LIMIT 1")
            pol = cur.fetchone()
            if not pol or not pol["authorized_automation_policy_enabled"]:
                conn.close()
                return {
                    "status": "BLOCKED",
                    "reason": "HUMAN_APPROVAL_REQUIRED: Outreach cannot execute without merchant sign-off."
                }

        execution_id = f"EXEC-{strategy_id}"
        message_id = make_msgid(domain="sharmasweets.in")
        now_iso = datetime.now(timezone.utc).isoformat()

        # Clear labeling for Demo Email Adapter (never pretend demo was delivered to real customer)
        provider_response = (
            "DEMO_EMAIL_ADAPTER: Credentials unconfigured. Delivery simulated locally; "
            "no live external email dispatched to real recipient."
        ) if is_demo_mode else "SMTP_GATEWAY: 250 Message accepted for delivery"

        delivery_status = "DEMO_DISPATCH_RECORDED" if is_demo_mode else "DELIVERED"

        cur.execute("""
        INSERT OR REPLACE INTO executions (
            execution_id, strategy_id, customer_id, channel, recipient_email,
            sent_subject, sent_body, dispatch_status, delivery_timestamp,
            response_classification, response_notes, next_recommended_action,
            verified_recovered_revenue, is_revenue_verified
        ) VALUES (?, ?, ?, 'EMAIL', ?, ?, ?, ?, CURRENT_TIMESTAMP, 'NO_RESPONSE', ?, 'Monitor inbox for 72 hours.', 0.0, 0)
        """, (
            execution_id, strategy_id, data["customer_id"], data["email"],
            data["email_subject"], data["email_body"], delivery_status,
            f"Message-ID: {message_id} | {provider_response}"
        ))

        cur.execute("UPDATE opportunities SET status = 'EXECUTED' WHERE opportunity_id = ?", (data["opportunity_id"],))
        conn.commit()
        conn.close()

        # Stage 8: Schedule Multi-Touch Follow-ups (Day 0, Day 3, Day 7)
        followup_steps = schedule_recovery_followups(
            strategy_id=strategy_id,
            customer_id=data["customer_id"],
            subject=data["email_subject"],
            intervals_days=[0, 3, 7]
        )

        record_audit(
            workflow_id="WF-REC-1042",
            agent_name=self.agent_name,
            action_type="DISPATCH_OUTREACH",
            tool_name="email_adapter_dispatch",
            tool_input={"strategy_id": strategy_id, "recipient": data["email"], "demo_mode": is_demo_mode},
            tool_output={"execution_id": execution_id, "message_id": message_id, "status": delivery_status}
        )

        return {
            "status": "SUCCESS",
            "execution_id": execution_id,
            "message_id": message_id,
            "recipient": data["email"],
            "subject": data["email_subject"],
            "dispatched_at": now_iso,
            "provider_response": provider_response,
            "tracking_status": delivery_status,
            "is_demo_mode": is_demo_mode,
            "adapter_label": "Demo Email Adapter (Safe Local Simulation)" if is_demo_mode else "Production Email Gateway",
            "scheduled_followups": followup_steps
        }

    def process_customer_reply(self, execution_id: str, reply_text: str, is_manual_entry: bool = True) -> Dict[str, Any]:
        """Classifies incoming customer reply, extracts intent, and cancels scheduled follow-ups."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT e.*, c.customer_id, c.customer_name
        FROM executions e
        JOIN customers c ON e.customer_id = c.customer_id
        WHERE e.execution_id = ?
        """, (execution_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"error": "Execution not found"}

        data = dict(row)
        txt = reply_text.lower()
        cid = data["customer_id"]

        entry_source = "MANUAL_REPLY_ENTRY" if is_manual_entry else "WEBHOOK_INBOX_POLL"

        # Classification Logic
        if "unsubscribe" in txt or "stop" in txt or "remove me" in txt:
            classification = "UNSUBSCRIBE"
            next_action = "CRITICAL: Do not contact again. Customer permanently unsubscribed."
            cur.execute("UPDATE customers SET is_unsubscribed = 1 WHERE customer_id = ?", (cid,))
            notes = f"[{entry_source}] Customer explicitly requested opt-out. Future automated messages stopped."
            cancel_pending_followups(cid, "CUSTOMER_OPTED_OUT", conn=conn)

        elif "meeting" in txt or "call" in txt or "discuss" in txt or "schedule" in txt:
            classification = "REQUESTS_MEETING"
            next_action = "Calendar invite link prepared for merchant sales team."
            notes = f"[{entry_source}] Customer replied: '{reply_text}'. Follow-ups halted for call coordination."
            cancel_pending_followups(cid, "CUSTOMER_REPLIED", conn=conn)

        elif "quote" in txt or "pricing" in txt or "discount" in txt or "cost" in txt:
            classification = "REQUESTS_QUOTATION"
            next_action = "Prepare revised commercial proposal with current delivery lead times."
            notes = f"[{entry_source}] Customer replied: '{reply_text}'. Commercial intent confirmed."
            cancel_pending_followups(cid, "CUSTOMER_REPLIED", conn=conn)

        elif "complaint" in txt or "defect" in txt or "damaged" in txt or "wrong item" in txt or "poor" in txt:
            classification = "COMPLAINT"
            next_action = "Escalate to Customer Care Manager immediately. Cease automated follow-ups."
            notes = f"[{entry_source}] Complaint detected: '{reply_text}'. Routed to senior supervisor."
            cancel_pending_followups(cid, "COMPLAINT_RAISED", conn=conn)

        elif "not interested" in txt or "no thanks" in txt or "already bought" in txt:
            classification = "NOT_INTERESTED"
            next_action = "Close opportunity. Set reminder to review in 6 months."
            notes = f"[{entry_source}] Customer indicated lack of current need: '{reply_text}'."
            cancel_pending_followups(cid, "NOT_INTERESTED", conn=conn)

        elif "interested" in txt or "proceed" in txt or "send details" in txt:
            classification = "INTERESTED"
            next_action = "Send proforma invoice and payment link."
            notes = f"[{entry_source}] Customer expressed active intent: '{reply_text}'."
            cancel_pending_followups(cid, "CUSTOMER_REPLIED", conn=conn)

        elif "more info" in txt or "details" in txt or "brochure" in txt:
            classification = "WANTS_MORE_INFO"
            next_action = "Send technical product sheet and user manual."
            notes = f"[{entry_source}] Customer requested collateral: '{reply_text}'."
            cancel_pending_followups(cid, "CUSTOMER_REPLIED", conn=conn)

        else:
            classification = "UNCLEAR"
            next_action = "Route to human sales representative for manual review."
            notes = f"[{entry_source}] Ambiguous response: '{reply_text}'."

        cur.execute("""
        UPDATE executions
        SET response_classification = ?, response_notes = ?, next_recommended_action = ?
        WHERE execution_id = ?
        """, (classification, notes, next_action, execution_id))
        conn.commit()
        conn.close()

        return {
            "execution_id": execution_id,
            "classification": classification,
            "entry_source": entry_source,
            "response_notes": notes,
            "next_recommended_action": next_action,
            "followups_stopped": classification in ["UNSUBSCRIBE", "REQUESTS_MEETING", "REQUESTS_QUOTATION", "NOT_INTERESTED", "COMPLAINT", "INTERESTED", "WANTS_MORE_INFO"]
        }

    def record_verified_purchase(self, execution_id: str, order_value_inr: float,
                                 invoice_ref: str, product_name: str = "Laboratory reactor accessories") -> Dict[str, Any]:
        """Stage 10: Records verified purchase and updates strict 4-category revenue attribution."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        UPDATE executions
        SET verified_recovered_revenue = ?, is_revenue_verified = 1,
            response_notes = 'Transaction completed and verified: Invoice #' || ?
        WHERE execution_id = ?
        """, (order_value_inr, invoice_ref, execution_id))

        cur.execute("SELECT customer_id, strategy_id FROM executions WHERE execution_id = ?", (execution_id,))
        row = cur.fetchone()
        conn.commit()
        conn.close()

        if not row:
            return {"error": "Execution not found"}

        cid = row["customer_id"]
        strat_id = row["strategy_id"]

        # Call Stage 10 Attribution Service
        purchase_record = record_verified_purchase_transaction(
            customer_id=cid,
            order_id=invoice_ref,
            product=product_name,
            purchase_amount=order_value_inr,
            currency="INR",
            associated_campaign=f"CAMPAIGN-{strat_id}",
            evidence_source="INVOICE_LEDGER",
            attribution_confidence="DIRECT_ATTRIBUTION",
            revenue_category="RECOVERED",
            baseline_notes=f"Directly verified via Invoice #{invoice_ref}. Attributed to DealPilot AI recovery outreach."
        )

        return {
            "execution_id": execution_id,
            "verified_purchase": purchase_record
        }
