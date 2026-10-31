"""DealPilot AI Agent 3: Recovery Strategy Agent.
Determines optimal communication strategy, tone, language, and generates personalized outreach drafts.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from ..database import get_connection
from ..integrations.sarvam import SarvamTranslate

class RecoveryStrategyAgent:
    """Selects best strategy, writes tailored outreach copy, and estimates commercial outcome."""

    def __init__(self, agent_name: str = "RecoveryStrategyAgent"):
        self.agent_name = agent_name

    def formulate_strategy(self, opportunity_id: str) -> Dict[str, Any]:
        """Analyzes opportunity and research to formulate exact recovery action and message."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT o.*, c.*, r.confirmed_facts, r.inferred_observations, r.research_summary
        FROM opportunities o
        JOIN customers c ON o.customer_id = c.customer_id
        LEFT JOIN customer_research r ON o.opportunity_id = r.opportunity_id
        WHERE o.opportunity_id = ?
        """, (opportunity_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"error": "Opportunity not found"}

        data = dict(row)
        q_status = data.get("quotation_status", "NONE")
        q_val = float(data.get("quotation_value", 0.0) or 0.0)
        product = data.get("interested_product", "your requirements")
        name = data.get("customer_name", "Valued Customer")
        company = data.get("company", "your organization")
        lang = data.get("preferred_language", "en")

        # 1. Strategy Selection Logic
        if q_status == "UNANSWERED" and q_val > 0:
            strategy_type = "QUOTATION_REMINDER"
            selected_tone = "CONSULTATIVE_PROFESSIONAL"
            justification = (
                f"Customer requested a quotation for {product} (value: ₹{q_val:,.0f}) "
                f"and has not responded. A consultative check-in is the highest-probability path to conversion."
            )
            subject = f"Following up regarding quotation for {product} — {company}"
            body = (
                f"Dear {name},\n\n"
                f"I hope you are having a productive week.\n\n"
                f"I am writing to follow up on the quotation we shared for {product} (Quotation Value: ₹{q_val:,.0f}). "
                f"We wanted to check if you had an opportunity to review the technical specifications and commercial terms.\n\n"
                f"If you need any adjustments to the scope, volume pricing, or delivery schedule, "
                f"we would be glad to arrange a brief discussion to tailor the proposal to your current timeline.\n\n"
                f"Looking forward to hearing from you.\n\n"
                f"Warm regards,\n"
                f"Ramesh Sharma\n"
                f"Sharma Sweets & Commercial Supplies"
            )
        elif q_status == "EXPIRED":
            strategy_type = "RE_ENGAGEMENT"
            selected_tone = "COURTEOUS_DIRECT"
            justification = f"Proposal validity for {product} lapsed. Re-engaging with updated validity terms."
            subject = f"Updated pricing and availability for {product} — {company}"
            body = (
                f"Dear {name},\n\n"
                f"We noticed that our previous quotation for {product} recently passed its standard validity window. "
                f"We value our partnership with {company} and would be delighted to provide an updated, priority quote "
                f"matching your upcoming quarterly requirements.\n\n"
                f"Please let us know if your procurement schedule is active for this month.\n\n"
                f"Warm regards,\nRamesh Sharma"
            )
        else:
            strategy_type = "FRIENDLY_FOLLOWUP"
            selected_tone = "FRIENDLY_APPRECIATIVE"
            justification = f"Customer has strong historical spend (₹{data.get('lifetime_value', 0):,.0f}) but no recent orders."
            subject = f"Checking in from Sharma Commercial Supplies — Special update for {name}"
            body = (
                f"Dear {name},\n\n"
                f"It has been a pleasure serving {company} in the past. We wanted to reach out and ensure "
                f"all your recent operations with our supplies are performing seamlessly.\n\n"
                f"We have updated our inventory for {product} and prepared exclusive seasonal terms for our priority patrons.\n\n"
                f"Could we share a concise one-page catalog with you?\n\n"
                f"Best regards,\nRamesh Sharma"
            )

        # Localize if preferred language is Indic
        if lang != "en":
            indic_body = translate_indic_live(body, lang)
            if indic_body:
                body = indic_body

        follow_up_date = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
        potential_val = q_val if q_val > 0 else float(data.get("last_purchase_value", 35000.0) or 35000.0)

        strategy_id = f"STRAT-{opportunity_id}"
        cur.execute("""
        INSERT OR REPLACE INTO recovery_strategies (
            strategy_id, opportunity_id, customer_id, strategy_type, selected_tone,
            communication_language, email_subject, email_body, customer_specific_context,
            strategy_justification, potential_commercial_value, recommended_follow_up_date,
            is_user_edited, approval_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'PENDING_APPROVAL')
        """, (
            strategy_id, opportunity_id, data["customer_id"], strategy_type, selected_tone,
            lang, subject, body, f"Interest: {product} | Quote: ₹{q_val:,.0f}",
            justification, potential_val, follow_up_date
        ))

        cur.execute("UPDATE opportunities SET status = 'STRATEGY_PLANNED' WHERE opportunity_id = ?", (opportunity_id,))
        conn.commit()
        conn.close()

        return {
            "strategy_id": strategy_id,
            "opportunity_id": opportunity_id,
            "strategy_type": strategy_type,
            "selected_tone": selected_tone,
            "communication_language": lang,
            "email_subject": subject,
            "email_body": body,
            "strategy_justification": justification,
            "potential_commercial_value": potential_val,
            "recommended_follow_up_date": follow_up_date,
            "approval_status": "PENDING_APPROVAL"
        }

    def update_draft(self, strategy_id: str, new_subject: str, new_body: str) -> bool:
        """Allows human operator to edit the AI-generated subject and body."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE recovery_strategies
        SET email_subject = ?, email_body = ?, is_user_edited = 1
        WHERE strategy_id = ?
        """, (new_subject, new_body, strategy_id))
        conn.commit()
        conn.close()
        return True

    def translate_strategy(self, strategy_id: str, target_lang: str) -> Dict[str, Any]:
        """Translates the recovery email draft into the target Indic language via Sarvam AI."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT s.*, c.customer_name, c.interested_product, c.quotation_value
        FROM recovery_strategies s
        JOIN customers c ON s.customer_id = c.customer_id
        WHERE s.strategy_id = ?
        """, (strategy_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return {"error": "Strategy not found"}

        data = dict(row)
        translator = SarvamTranslate()
        res = translator.translate_message(
            text=data["email_body"],
            target_lang=target_lang,
            source_lang="en",
            product=data.get("interested_product", ""),
            price=float(data.get("quotation_value", 0.0) or 0.0),
            customer_name=data.get("customer_name", "")
        )
        return {
            "strategy_id": strategy_id,
            "target_language": target_lang,
            "translated_subject": data["email_subject"],
            "translated_body": res["translated_text"],
            "provider": res["provider"],
            "is_fallback": res.get("is_fallback", False)
        }

