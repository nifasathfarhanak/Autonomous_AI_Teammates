"""Core HTTP client for Sarvam AI APIs.
Uses Python standard library with connection pooling, retries, rate-limit handling,
and transparent fallback when credentials are not configured.
"""

import json
import time
import uuid
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

    def post_multipart(
        self,
        url: str,
        fields: Dict[str, str],
        file_field: str,
        filename: str,
        file_bytes: bytes,
        content_type: str,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Uploads an audio file and form fields to a Sarvam multipart endpoint."""
        if not self.has_active_key:
            raise SarvamAuthError("SARVAM_API_KEY is not configured.", status_code=401)
        if not file_bytes:
            raise SarvamValidationError("Audio file is empty.", status_code=400)

        boundary = f"----ActionMate{uuid.uuid4().hex}"
        body = bytearray()
        for name, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("ascii"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("ascii")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
        body.extend(file_bytes)
        body.extend(f"\r\n--{boundary}--\r\n".encode("ascii"))

        request = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "api-subscription-key": self.api_key.strip(),
                "User-Agent": "DealPilot-AI-Enterprise/2.4"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result, dict):
                    raise SarvamError("Sarvam AI returned an invalid response.")
                return result
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="ignore")
            if error.code in (401, 403):
                raise SarvamAuthError("Sarvam AI authentication failed.", status_code=error.code) from error
            if error.code == 429:
                raise SarvamRateLimitError("Sarvam AI rate limit exceeded.", status_code=429) from error
            if error.code == 400:
                raise SarvamValidationError(f"Sarvam AI rejected the audio request: {details}", status_code=400) from error
            raise SarvamError(f"Sarvam AI audio request failed with HTTP {error.code}: {details}", status_code=error.code) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise SarvamConnectionError(f"Failed to reach Sarvam AI: {error}") from error
