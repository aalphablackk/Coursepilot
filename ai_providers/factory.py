
from django.conf import settings

from .base import BaseAIProvider
from .exceptions import AIProviderError
from .gemini import GeminiProvider
from .openai import OpenAIProvider


PROVIDER_CLASSES = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def get_ai_provider(
    provider_name: str | None = None,
) -> BaseAIProvider:
    """
    Return the configured provider.

    Explicit provider selection is supported for internal use.
    Account-level authorization must be enforced when accounts
    are implemented.
    """
    configured_default = getattr(settings, "AI_PROVIDER", "gemini")

    if not isinstance(configured_default, str):
        raise AIProviderError("AI_PROVIDER must be a provider name.")

    selected_provider = (
        provider_name if provider_name is not None else configured_default
    )

    if not isinstance(selected_provider, str) or not selected_provider.strip():
        raise AIProviderError("An AI provider must be specified.")

    selected_provider = selected_provider.strip().lower()
    provider_class = PROVIDER_CLASSES.get(selected_provider)

    if provider_class is None:
        raise AIProviderError(
            f"Unsupported AI provider: {selected_provider}"
        )

    # The provider constructor checks whether its API key is configured.
    return provider_class()
