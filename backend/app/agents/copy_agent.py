"""DealPilot AI Agent 3: DealScribe (Communications & Copywriter Agent).
Generates localized, high-converting messages in English and 7 Indic languages powered by Sarvam AI.
"""

from typing import Dict, Any
from ..services.sarvam_service import generate_indic_bundle, get_soundbox_voice_script
from ..services.email_service import generate_email_mime

class DealScribeAgent:
    """Specialized in regional language localization, tone calibration, and email/WhatsApp copy drafting."""

    def __init__(self, agent_name: str = "DealScribe"):
        self.agent_name = agent_name

    def draft_multilingual_bundle(self, discount: float, min_order: float, code: str) -> Dict[str, str]:
        """Drafts localized campaign copy using Sarvam AI Indic Sovereign models."""
        return generate_indic_bundle(discount=discount, min_order=min_order, code=code)

    def prepare_email_template(self, customer_name: str, email: str, discount_code: str,
                               discount_amount: float, min_order: float, store_name: str) -> Dict[str, Any]:
        """Generates RFC-822 MIME email payload with deliverability headers."""
        return generate_email_mime(
            customer_name=customer_name,
            recipient_email=email,
            discount_code=discount_code,
            discount_amount=discount_amount,
            min_order=min_order,
            store_name=store_name
        )

    def get_soundbox_audio(self, lang: str = "en") -> str:
        """Returns the spoken text script for Paytm Soundbox 4.0 playback."""
        return get_soundbox_voice_script(lang=lang)
