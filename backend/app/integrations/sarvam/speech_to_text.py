"""Saaras v4 speech-to-text integration for merchant voice queries.
"""

from typing import Dict, Any, Optional
from .client import SarvamClient
from .config import ENDPOINTS, MODEL_STT
from .exceptions import SarvamError

class SaarasSTT:
    """Transcribes recorded merchant questions with the Sarvam Saaras API."""

    def __init__(self, client: Optional[SarvamClient] = None):
        self.client = client or SarvamClient()

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        content_type: str = "audio/webm"
    ) -> Dict[str, Any]:
        """Transcribes an audio recording and returns the recognized language."""
        if not audio_bytes:
            return {"error": "No audio was recorded.", "provider": "SARVAM_SAARAS_V4"}

        if not self.client.is_connected():
            return {
                "error": "SARVAM_API_KEY is not configured. Speech recognition is unavailable.",
                "language_code": language_code,
                "provider": "SARVAM_SAARAS_UNAVAILABLE"
            }

        filename = "merchant-question.webm"
        if content_type == "audio/mp4":
            filename = "merchant-question.mp4"
        elif content_type == "audio/wav":
            filename = "merchant-question.wav"
        elif content_type == "audio/ogg":
            filename = "merchant-question.ogg"

        try:
            result = self.client.post_multipart(
                ENDPOINTS["speech_to_text"],
                {"model": MODEL_STT, "language_code": language_code},
                "file",
                filename,
                audio_bytes,
                content_type
            )
            transcript = result.get("transcript")
            if not isinstance(transcript, str) or not transcript.strip():
                return {
                    "error": "Sarvam could not recognize speech in this recording. Please try again.",
                    "language_code": result.get("language_code") or language_code,
                    "provider": "SARVAM_SAARAS_V4"
                }
            return {
                "transcript": transcript.strip(),
                "language_code": result.get("language_code") or language_code,
                "request_id": result.get("request_id"),
                "provider": "SARVAM_SAARAS_V4"
            }
        except SarvamError as e:
            return {
                "error": str(e),
                "language_code": language_code,
                "provider": "SARVAM_SAARAS_ERROR"
            }
