"""Custom exceptions for Sarvam AI Integration."""

class SarvamError(Exception):
    """Base exception for all Sarvam AI errors."""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class SarvamAuthError(SarvamError):
    """Raised when API key is missing, invalid, or unauthorized."""
    pass

class SarvamRateLimitError(SarvamError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass

class SarvamConnectionError(SarvamError):
    """Raised when unable to reach the Sarvam AI gateway."""
    pass

class SarvamValidationError(SarvamError):
    """Raised when request payload or parameters are invalid."""
    pass

