"""DealPilot AI - Sarvam AI Indic Sovereign Integration Package.
Provides client, chat (105B), translate (Mayura), STT (Saaras), and TTS (Bulbul).
"""

from .client import SarvamClient
from .chat import SarvamChat
from .translate import SarvamTranslate
from .speech_to_text import SaarasSTT
from .text_to_speech import BulbulTTS
from .config import SUPPORTED_LANGUAGES, MODEL_CHAT_105B, MODEL_TRANSLATE, MODEL_STT, MODEL_TTS
from .exceptions import SarvamError, SarvamAuthError, SarvamRateLimitError

__all__ = [
    "SarvamClient",
    "SarvamChat",
    "SarvamTranslate",
    "SaarasSTT",
    "BulbulTTS",
    "SUPPORTED_LANGUAGES",
    "MODEL_CHAT_105B",
    "MODEL_TRANSLATE",
    "MODEL_STT",
    "MODEL_TTS",
    "SarvamError",
    "SarvamAuthError",
    "SarvamRateLimitError"
]

