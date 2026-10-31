"""Sarvam-105B Reasoning and Strategy Agent Client.
Official Model Identifier: sarvam-105b
Used for contextual reasoning, epistemic report synthesis, and structured JSON output.
"""

from typing import Dict, Any, List, Optional
from .client import SarvamClient
from .config import ENDPOINTS, MODEL_CHAT_105B
from .schemas import validate_chat_payload

class SarvamChat:
    """Interacts with Sarvam-105B for contextual business reasoning."""

    def __init__(self, client: Optional[SarvamClient] = None):
        self.client = client or SarvamClient()

    def generate_recovery_reasoning(self, customer_context: Dict[str, Any]) -> Dict[str, Any]:
        """Uses Sarvam-105B (or deterministic fallback) to formulate recovery recommendations."""
        if not self.client.is_connected():
            return self._fallback_reasoning(customer_context)

        system_prompt = (
            "You are DealPilot AI Strategy Specialist. Analyze the provided customer data, "
            "purchase history, and quotation records. Output a structured recovery strategy "
            "with strategy_type, selected_tone, email_subject, and email_body. Preserve all product names and numbers."
        )

        user_prompt = f"Customer Context: {customer_context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            payload = validate_chat_payload(messages, temperature=0.1, max_tokens=1024)
            resp = self.client.post(ENDPOINTS["chat"], payload)
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "source": "SARVAM_105B_LIVE",
                "model": MODEL_CHAT_105B,
                "content": content
            }
        except Exception:
            return self._fallback_reasoning(customer_context)

    def _fallback_reasoning(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """High-fidelity grounded reasoning when live LLM is offline."""
        q_status = ctx.get("quotation_status", "NONE")
        q_val = float(ctx.get("quotation_value", 0.0) or 0.0)
        cname = ctx.get("customer_name", "Valued Customer")
        product = ctx.get("interested_product", "your requirements")
        company = ctx.get("company", "your organization")

        if q_status in ("UNANSWERED", "SENT") and q_val > 0:
            strategy_type = "QUOTATION_REMINDER"
            tone = "CONSULTATIVE_PROFESSIONAL"
            subject = f"Following up regarding quotation for {product} — {company}"
            body = (
                f"Dear {cname},\n\n"
                f"I hope you are having a productive week.\n\n"
                f"I am writing to follow up on the quotation we shared for {product} (Quotation Value: ₹{q_val:,.0f}). "
                f"We wanted to check if you had an opportunity to review the technical specifications and commercial terms.\n\n"
                f"If you need any adjustments to the scope, volume pricing, or delivery schedule, "
                f"we would be glad to arrange a brief discussion to tailor the proposal to your current timeline.\n\n"
                f"Looking forward to hearing from you.\n\n"
                f"Warm regards,\n"
                f"Ramesh Sharma\n"
                f"Sharma Commercial & Industrial Supplies"
            )
        else:
            strategy_type = "FRIENDLY_FOLLOWUP"
            tone = "FRIENDLY_APPRECIATIVE"
            subject = f"Checking in from Sharma Commercial Supplies — Update for {cname}"
            body = (
                f"Dear {cname},\n\n"
                f"It has been a pleasure serving {company} in the past. We wanted to reach out and ensure "
                f"all your recent operations with our supplies are performing seamlessly.\n\n"
                f"We have updated our catalog for {product} and prepared exclusive seasonal terms for our priority patrons.\n\n"
                f"Could we share a concise one-page catalog with you?\n\n"
                f"Warm regards,\nRamesh Sharma"
            )

        return {
            "source": "DEALPILOT_DETERMINISTIC_REASONING_ENGINE",
            "model": "sarvam-105b-fallback",
            "strategy_type": strategy_type,
            "selected_tone": tone,
            "email_subject": subject,
            "email_body": body
        }

