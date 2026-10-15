
from abc import ABC, abstractmethod
from typing import Any

from .schemas import AIResponse


class BaseAIProvider(ABC):
    """Common interface implemented by every AI generation provider."""

    provider_name: str

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
        **kwargs: Any,
    ) -> AIResponse:
        """Generate text and return a normalized response."""
        raise NotImplementedError
