import unittest
from unittest.mock import Mock, patch

from backend.app.integrations.sarvam.client import SarvamClient
from backend.app.integrations.sarvam.config import ENDPOINTS, MODEL_STT
from backend.app.integrations.sarvam.speech_to_text import SaarasSTT
from backend.app.integrations.sarvam.text_to_speech import BulbulTTS
from backend.app.services.voice_copilot_service import VoiceCopilotService
from backend.app.server import voice_copilot_service
from backend.tests.test_hackathon_demo_readiness import DummyHandler


class TestSarvamVoiceIntegration(unittest.TestCase):
    def test_saaras_uploads_recording_and_returns_recognized_text(self):
        client = SarvamClient(api_key="test-key-for-voice")
        stt = SaarasSTT(client)
        audio = b"recorded-audio"
        with patch.object(client, "post_multipart", return_value={
            "transcript": "How are my sales?",
            "language_code": "en-IN",
            "request_id": "request-123"
        }) as post_multipart:
            result = stt.transcribe_audio(audio, "en-IN", "audio/mp4")

        self.assertEqual(result["transcript"], "How are my sales?")
        self.assertEqual(result["language_code"], "en-IN")
        self.assertEqual(result["provider"], "SARVAM_SAARAS_V4")
        post_multipart.assert_called_once_with(
            ENDPOINTS["speech_to_text"],
            {"model": MODEL_STT, "language_code": "en-IN"},
            "file",
            "merchant-question.mp4",
            audio,
            "audio/mp4"
        )

    def test_saaras_reports_empty_recording_without_calling_provider(self):
        client = SarvamClient(api_key="test-key-for-voice")
        stt = SaarasSTT(client)
        with patch.object(client, "post_multipart") as post_multipart:
            result = stt.transcribe_audio(b"", "hi-IN")

        self.assertIn("No audio", result["error"])
        post_multipart.assert_not_called()

    def test_bulbul_uses_language_default_speaker_and_returns_audio(self):
        client = SarvamClient(api_key="test-key-for-voice")
        tts = BulbulTTS(client)
        with patch.object(client, "post", return_value={"audios": ["UklGR-audio"]}) as post:
            result = tts.generate_speech("नमस्ते", "hi-IN")

        self.assertEqual(result["audio_base64"], "UklGR-audio")
        self.assertEqual(result["speaker"], "priya_hi_recovery")
        self.assertEqual(result["provider"], "SARVAM_BULBUL_LIVE")
        payload = post.call_args.args[1]
        self.assertEqual(payload["target_language_code"], "hi-IN")
        self.assertEqual(payload["model"], "bulbul:v4-flash")

    def test_voice_service_reports_missing_key_without_fake_audio(self):
        service = VoiceCopilotService()
        with patch.object(service.sarvam_client, "is_connected", return_value=False):
            result = service.synthesize_speech("A spoken answer", "hi-IN")

        self.assertIsNone(result.get("audio_base64"))
        self.assertIn("SARVAM_API_KEY", result["error"])

    def test_voice_service_passes_language_default_to_bulbul(self):
        service = VoiceCopilotService()
        service.tts.generate_speech = Mock(return_value={
            "audio_base64": "UklGR-audio",
            "provider": "SARVAM_BULBUL_LIVE"
        })
        with patch.object(service.sarvam_client, "is_connected", return_value=True):
            result = service.synthesize_speech("A spoken answer", "hi-IN")

        self.assertEqual(result["audio_base64"], "UklGR-audio")
        service.tts.generate_speech.assert_called_once_with("A spoken answer", "hi-IN", None)

    def test_voice_reply_is_translated_to_the_selected_language(self):
        service = VoiceCopilotService()
        with patch.object(service.sarvam_client, "is_connected", return_value=True), \
             patch.object(service.sarvam_client, "post", return_value={
                 "translated_text": "உங்கள் விற்பனை நன்றாக உள்ளது."
             }) as post:
            translated, error = service._translate_reply("Your sales are doing well.", "ta-IN")

        self.assertEqual(translated, "உங்கள் விற்பனை நன்றாக உள்ளது.")
        self.assertIsNone(error)
        self.assertEqual(post.call_args.args[1]["target_language_code"], "ta-IN")

    def test_voice_reply_reports_unavailable_translation_instead_of_faking_it(self):
        service = VoiceCopilotService()
        with patch.object(service.sarvam_client, "is_connected", return_value=False):
            translated, error = service._translate_reply("Your sales are doing well.", "ta-IN")

        self.assertEqual(translated, "Your sales are doing well.")
        self.assertIn("Set SARVAM_API_KEY", error)

    def test_transcription_endpoint_forwards_audio_and_mime_type(self):
        audio = b"recorded-audio"
        with patch.object(voice_copilot_service, "transcribe_audio_payload", return_value={
            "transcript": "How are my sales?",
            "provider": "SARVAM_SAARAS_V4"
        }) as transcribe:
            handler = DummyHandler("POST", "/api/voice/transcribe", {
                "audio_base64": "cmVjb3JkZWQtYXVkaW8=",
                "content_type": "audio/mp4",
                "language_code": "en-IN"
            })
            handler.do_POST()

        self.assertEqual(handler.status_code, 200)
        self.assertEqual(handler.get_response_json()["transcript"], "How are my sales?")
        transcribe.assert_called_once_with(audio, "en-IN", "audio/mp4")

    def test_transcription_endpoint_rejects_missing_audio(self):
        handler = DummyHandler("POST", "/api/voice/transcribe", {
            "audio_base64": "",
            "content_type": "audio/webm"
        })
        handler.do_POST()

        self.assertEqual(handler.status_code, 400)
        self.assertIn("No audio", handler.get_response_json()["error"])


if __name__ == "__main__":
    unittest.main()
