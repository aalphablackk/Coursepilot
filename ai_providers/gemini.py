
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

from .base import BaseAIProvider
from .exceptions import (
    AIProviderNotConfiguredError,
    AIProviderResponseError,
    AIProviderUnavailableError,
)


class GeminiProvider(BaseAIProvider):
    provider_name = "gemini"

    def __init__(self) -> None:
        api_key = getattr(settings, "GEMINI_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "Gemini is not configured on this server."
            )

        self.model = getattr(
            settings,
            "GEMINI_MODEL",
            "gemini-3.8-flash",
        )
        self.client = genai.Client(api_key=api_key)

    
    def __init__(self) -> None:
        api_key = getattr(settings, "GEMINI_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "Gemini is not configured on this server."
            )

        self.model = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
        self.fallback_model = getattr(settings, "GEMINI_FALLBACK_MODEL", "")
        self.client = genai.Client(api_key=api_key)


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

        config_options: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

        if system_instruction:
            config_options["system_instruction"] = system_instruction

        models_to_try = [self.model]

        if self.fallback_model and self.fallback_model != self.model:
            models_to_try.append(self.fallback_model)

        last_error = None

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_options),
                )
            except Exception as exc:
                last_error = exc
                continue

            text = getattr(response, "text", None)

            if isinstance(text, str) and text.strip():
                return text.strip()

            last_error = ValueError(
                f"Gemini model '{model_name}' returned no usable text."
            )

        raise AIProviderUnavailableError(
            "Gemini could not complete the request using the configured models."
        ) from last_error
