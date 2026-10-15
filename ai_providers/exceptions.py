    
class AIProviderError(Exception):
    """Base exception for AI provider errors."""


class AIProviderNotConfiguredError(AIProviderError):
    """Raised when a provider is missing required configuration."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when a provider cannot complete a request."""


class AIProviderResponseError(AIProviderError):
    """Raised when a provider returns an invalid or unusable response."""
