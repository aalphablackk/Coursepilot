
from typing import Any

from django.conf import settings
from openai import OpenAI

from .base import BaseAIProvider
from .exceptions import (
    AIProviderNotConfiguredError,
    AIProviderResponseError,
    AIProviderUnavailableError,
)


class OpenAIProvider(BaseAIProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        api_key = getattr(settings, "OPENAI_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "OpenAI is not configured on this server."
            )

        self.model = getattr(
            settings,
            "OPENAI_MODEL",
            "gpt-4.1-mini",
        )
        self.client = OpenAI(api_key=api_key)

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
        **kwargs: Any,
    ) -> str:
        if not prompt.strip():
            raise AIProviderResponseError("The prompt cannot be empty.")

        messages = []

        if system_instruction:
            messages.append({
                "role": "system",
                "content": system_instruction,
            })

        messages.append({
            "role": "user",
            "content": prompt,
        })

        try:
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise AIProviderUnavailableError(
                "OpenAI could not complete the request. Please try again."
            ) from exc

        text = getattr(response, "output_text", None)

        if not isinstance(text, str) or not text.strip():
            raise AIProviderResponseError(
                "OpenAI returned no usable text."
            )

        return text.strip()
