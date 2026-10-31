"""Bulbul v4 Flash Text-to-Speech Integration.
Generates natural Indic speech audio from outreach messages and voice announcements.
"""

from typing import Dict, Any, Optional
from .client import SarvamClient
from .config import ENDPOINTS, MODEL_TTS
from .schemas import validate_tts_payload

class BulbulTTS:
    """Generates natural audio previews using Bulbul v4 Flash."""

    def __init__(self, client: Optional[SarvamClient] = None):
        self.client = client or SarvamClient()

    def generate_speech(self, text: str, language_code: str = "hi") -> Dict[str, Any]:
        """Converts text into audio stream or base64 WAV payload."""
        if not self.client.is_connected():
            return {
                "audio_url": None,
                "audio_base64_sample": None,
                "duration_seconds": 4.8,
                "speaker": "meera",
                "language": language_code,
                "provider": "BULBUL_TTS_SIMULATION",
                "message": "Bulbul TTS preview generated in simulation mode."
            }

        try:
            payload = validate_tts_payload(text, language_code)
            res = self.client.post(ENDPOINTS["text_to_speech"], payload)
            audios = res.get("audios", [])
            speaker = payload.get("speaker", "priya_hi_recovery")
            return {
                "audio_base64": audios[0] if audios else None,
                "duration_seconds": 5.2,
                "speaker": speaker,
                "language": language_code,
                "provider": "SARVAM_BULBUL_LIVE"
            }
        except Exception as e:
            return {
                "error": str(e),
                "audio_url": None,
                "provider": "BULBUL_TTS_ERROR"
            }

