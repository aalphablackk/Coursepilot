
from typing import Any

from django.conf import settings
from google import genai
from google.genai import types

from .base import BaseAIProvider
from .exceptions import (
    AIProviderError,
    AIProviderAuthenticationError,
    AIProviderNotConfiguredError,
    AIProviderQuotaExceededError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTemporaryError,
    AIProviderUnavailableError,
)
from .schemas import AIResponse, AIUsage


class GeminiProvider(BaseAIProvider):
    provider_name = "gemini"

    def __init__(self) -> None:
        api_key = getattr(settings, "GEMINI_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "Gemini is not configured on this server."
            )

        self.model = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
        self.fallback_model = getattr(settings, "GEMINI_FALLBACK_MODEL", "")
        self.client = genai.Client(api_key=api_key)


    @staticmethod
    def _raise_api_error(exc: Exception) -> None:
        """Translate Gemini SDK errors into CoursePilot error types."""

        # Preserve errors that have already been classified.
        if isinstance(exc, AIProviderAuthenticationError):
            raise exc

        if isinstance(exc, AIProviderQuotaExceededError):
            raise exc

        if isinstance(exc, AIProviderRateLimitError):
            raise exc

        if isinstance(exc, AIProviderTemporaryError):
            raise exc

        if isinstance(exc, AIProviderUnavailableError):
            raise exc

        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            status_code = getattr(exc, "code", None)

        status_text = str(status_code).lower()
        message = str(exc).lower()



        if status_text in {"401", "403", "unauthenticated", "permission_denied"}:
            raise AIProviderAuthenticationError(
                "Gemini authentication failed. Check the configured API credentials and permissions."
            ) from exc

        if status_text in {"429", "resource_exhausted"}:
            if any(term in message for term in (
                "quota",
                "billing",
                "limit: 0",
                "insufficient",
            )):
                raise AIProviderQuotaExceededError(
                    "Gemini usage quota or billing limit has been reached."
                ) from exc

            raise AIProviderRateLimitError(
                "Gemini is limiting requests. Please try again shortly."
            ) from exc

        if status_text in {
            "500", "502", "503", "504",
            "internal", "unavailable", "deadline_exceeded",
        }:
            raise AIProviderTemporaryError(
                "Gemini is temporarily unavailable. Please try again shortly."
            ) from exc

        raise AIProviderUnavailableError(
            "Gemini could not complete the request. Please try again."
        ) from exc

    def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int = 8192,
        **kwargs: Any,
    ) -> AIResponse:
        if not isinstance(prompt, str) or not prompt.strip():
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

        last_error: Exception | None = None

        for index, model_name in enumerate(models_to_try):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_options),
                )

            except Exception as exc:
                last_error = exc

                try:
                    self._raise_api_error(exc)
                except (
                    AIProviderAuthenticationError,
                    AIProviderQuotaExceededError,
                ):
                    # These failures will not be fixed by changing models.
                    raise
                except (
                    AIProviderTemporaryError,
                    AIProviderRateLimitError,
                    AIProviderUnavailableError,
                ):
                    # Try the configured fallback if one remains.
                    if index + 1 < len(models_to_try):
                        continue
                    raise


            text = getattr(response, "text", None)
            if not isinstance(text, str) or not text.strip():
                last_error = ValueError("Gemini returned no usable text.")
                if index + 1 < len(models_to_try):
                    continue
                raise AIProviderResponseError(
                    "Gemini returned no usable text."
                ) from last_error

            usage_metadata = getattr(response, "usage_metadata", None)
            candidate = None
            candidates = getattr(response, "candidates", None)
            if candidates:
                candidate = candidates[0]

            finish_reason = getattr(candidate, "finish_reason", None)
            if finish_reason is not None:
                finish_reason = str(
                    getattr(finish_reason, "name", finish_reason)
                )

            return AIResponse(
                content=text.strip(),
                provider=self.provider_name,
                model=model_name,
                usage=AIUsage(
                    input_tokens=getattr(
                        usage_metadata, "prompt_token_count", None
                    ),
                    output_tokens=getattr(
                        usage_metadata, "candidates_token_count", None
                    ),
                    total_tokens=getattr(
                        usage_metadata, "total_token_count", None
                    ),
                ),
                finish_reason=finish_reason,
                request_id=None,
                metadata={},
            )

        raise AIProviderUnavailableError(
            "Gemini could not complete the request using the configured models."
        ) from last_error
