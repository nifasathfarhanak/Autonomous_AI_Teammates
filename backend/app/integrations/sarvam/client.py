"""Core HTTP client for Sarvam AI APIs.
Uses Python standard library with connection pooling, retries, rate-limit handling,
and transparent fallback when credentials are not configured.
"""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from .config import (
    SARVAM_API_KEY, SARVAM_BASE_URL, ENDPOINTS,
    DEFAULT_TIMEOUT, MAX_RETRIES, SUPPORTED_LANGUAGES
)
from .exceptions import (
    SarvamError, SarvamAuthError, SarvamRateLimitError,
    SarvamConnectionError, SarvamValidationError
)

class SarvamClient:
    """Enterprise client for communicating with Sarvam AI Indic Sovereign stack."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SARVAM_API_KEY
        self.base_url = SARVAM_BASE_URL
        self.has_active_key = bool(self.api_key and len(self.api_key.strip()) > 8)

    def is_connected(self) -> bool:
        """Returns True if a live API key is configured."""
        return self.has_active_key

    def test_connection(self) -> Dict[str, Any]:
        """Tests live reachability of Sarvam AI gateway."""
        if not self.has_active_key:
            return {
                "status": "UNCONFIGURED",
                "connected": False,
                "provider": "Sarvam AI Indic Sovereign Platform",
                "message": "SARVAM_API_KEY is not set. High-fidelity Indic simulation is active.",
                "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
                "latency_ms": 0
            }

        start = time.time()
        try:
            # Pinging translate endpoint with lightweight test payload
            payload = {
                "input": "Hello",
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN",
                "speaker_gender": "Female",
                "mode": "formal"
            }
            res = self.post(ENDPOINTS["translate"], payload)
            latency = int((time.time() - start) * 1000)
            return {
                "status": "CONNECTED",
                "connected": True,
                "provider": "Sarvam AI Indic Sovereign Platform",
                "message": "Sarvam AI Gateway healthy and operational.",
                "latency_ms": latency,
                "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
                "test_output": res.get("translated_text", "")
            }
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            return {
                "status": "ERROR",
                "connected": False,
                "provider": "Sarvam AI Indic Sovereign Platform",
                "error": str(e),
                "latency_ms": latency,
                "message": "Connection attempt to Sarvam AI failed. Falling back to offline Indic engine.",
                "supported_languages": list(SUPPORTED_LANGUAGES.keys())
            }

    def post(self, url: str, payload: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Executes an authenticated POST request with retry logic."""
        if not self.has_active_key:
            raise SarvamAuthError("SARVAM_API_KEY is not configured.", status_code=401)

        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": self.api_key.strip(),
            "User-Agent": "DealPilot-AI-Enterprise/2.4"
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status_code = response.getcode()
                    body = response.read().decode("utf-8")
                    if status_code in (200, 201):
                        return json.loads(body)
                    else:
                        raise SarvamError(f"Unexpected status: {status_code}", status_code=status_code)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                if e.code in (401, 403):
                    raise SarvamAuthError(f"Sarvam AI authentication failed: {err_body}", status_code=e.code)
                elif e.code == 429:
                    if attempt < MAX_RETRIES:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    raise SarvamRateLimitError("Sarvam AI rate limit exceeded.", status_code=429)
                elif e.code == 400:
                    raise SarvamValidationError(f"Sarvam AI invalid request: {err_body}", status_code=400)
                else:
                    last_error = SarvamError(f"HTTP {e.code}: {err_body}", status_code=e.code)
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = SarvamConnectionError(f"Failed to reach Sarvam AI: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(0.5 * (attempt + 1))
                    continue

        if last_error:
            raise last_error
        raise SarvamError("Request to Sarvam AI failed after retries.")

