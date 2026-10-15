
class AIProviderError(Exception):
    """Base exception for AI provider errors."""


class AIProviderNotConfiguredError(AIProviderError):
    """Raised when a provider is missing required configuration."""


class AIProviderAuthenticationError(AIProviderError):
    """Raised when provider credentials are invalid or unauthorized."""


class AIProviderQuotaExceededError(AIProviderError):
    """Raised when the account's usage quota or billing limit is exhausted."""


class AIProviderRateLimitError(AIProviderError):
    """Raised when a provider temporarily limits request frequency."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when a provider cannot complete a request."""


class AIProviderTemporaryError(AIProviderUnavailableError):
    """Raised for temporary failures that may succeed on retry."""


class AIProviderResponseError(AIProviderError):
    """Raised when a provider returns an invalid or unusable response."""
