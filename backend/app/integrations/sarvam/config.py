"""Sarvam AI Configuration and Endpoint Specifications.
Based on official Sarvam AI API documentation (https://docs.sarvam.ai/).
"""

import os
from typing import Dict

from ...config import SARVAM_API_KEY
SARVAM_BASE_URL = os.environ.get("SARVAM_BASE_URL", "https://api.sarvam.ai")

# Official model identifiers
MODEL_CHAT_105B = "sarvam-105b"
MODEL_TRANSLATE = "mayura:v1"
MODEL_STT = "saaras:v2"
MODEL_TTS = "bulbul:v4-flash"

# Endpoint paths
ENDPOINTS = {
    "chat": f"{SARVAM_BASE_URL}/v1/chat/completions",
    "translate": f"{SARVAM_BASE_URL}/translate",
    "speech_to_text": f"{SARVAM_BASE_URL}/speech-to-text",
    "text_to_speech": f"{SARVAM_BASE_URL}/text-to-speech",
}

# Supported Indic Languages mapping
SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "en": {"code": "en-IN", "name": "English", "native": "English"},
    "hi": {"code": "hi-IN", "name": "Hindi", "native": "हिन्दी"},
    "ta": {"code": "ta-IN", "name": "Tamil", "native": "தமிழ்"},
    "te": {"code": "te-IN", "name": "Telugu", "native": "తెలుగు"},
    "kn": {"code": "kn-IN", "name": "Kannada", "native": "ಕನ್ನಡ"},
    "bn": {"code": "bn-IN", "name": "Bengali", "native": "বাংলা"},
    "mr": {"code": "mr-IN", "name": "Marathi", "native": "मराठी"},
    "gu": {"code": "gu-IN", "name": "Gujarati", "native": "ગુજરાતી"},
    "ml": {"code": "ml-IN", "name": "Malayalam", "native": "മലയാളം"},
    "pa": {"code": "pa-IN", "name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    "od": {"code": "od-IN", "name": "Odia", "native": "ଓଡ଼ିଆ"},
}

DEFAULT_TIMEOUT = 10.0  # seconds
MAX_RETRIES = 2

