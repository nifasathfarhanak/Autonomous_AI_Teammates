"""Data schemas for Sarvam AI requests and responses."""

from typing import Dict, Any, List, Optional

def validate_translate_payload(input_text: str, source_lang: str, target_lang: str) -> Dict[str, Any]:
    """Validates and formats the payload for Sarvam-Translate."""
    if not input_text or not input_text.strip():
        raise ValueError("Input text cannot be empty.")
    
    # Map short codes (e.g. 'en') to official codes (e.g. 'en-IN')
    src = source_lang if "-" in source_lang else f"{source_lang}-IN"
    tgt = target_lang if "-" in target_lang else f"{target_lang}-IN"
    
    return {
        "input": input_text.strip(),
        "source_language_code": src,
        "target_language_code": tgt,
        "speaker_gender": "Female",
        "mode": "formal",
        "model": "mayura:v1",
        "enable_preprocessing": True
    }

def validate_chat_payload(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1024) -> Dict[str, Any]:
    """Validates and formats the payload for Sarvam-105B."""
    if not messages:
        raise ValueError("Messages list cannot be empty.")
    return {
        "model": "sarvam-105b",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

SPEAKERS_BY_LANG = {
    "hi": "priya_hi_recovery",
    "en": "dev_en_recovery",
    "ta": "gokul_ta_narration",
    "te": "kavitha_te_conversation",
    "kn": "chaitra_kn_conversation",
    "bn": "roopa_bn_conversational",
    "mr": "ishita_mr_conversational",
    "gu": "pooja_gu_customer",
    "pa": "anand_pa_customer",
}

def validate_tts_payload(text: str, target_lang: str = "hi", speaker: Optional[str] = None) -> Dict[str, Any]:
    """Validates and formats the payload for Bulbul v4 Flash TTS."""
    lang_key = target_lang.split("-")[0].lower() if target_lang else "hi"
    tgt = target_lang if "-" in target_lang else f"{lang_key}-IN"
    selected_speaker = speaker or SPEAKERS_BY_LANG.get(lang_key, "priya_hi_recovery")

    return {
        "inputs": [text.strip()],
        "target_language_code": tgt,
        "speaker": selected_speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v4-flash"
    }

