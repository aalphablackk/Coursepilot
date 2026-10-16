
from typing import Any

import openai
from django.conf import settings
from openai import OpenAI

from .base import BaseAIProvider
from .exceptions import (
    AIProviderAuthenticationError,
    AIProviderNotConfiguredError,
    AIProviderQuotaExceededError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTemporaryError,
    AIProviderUnavailableError,
)
from .schemas import AIResponse, AIUsage


class OpenAIProvider(BaseAIProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        api_key = getattr(settings, "OPENAI_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "OpenAI is not configured on this server."
            )

        self.model = getattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _raise_api_error(exc: Exception) -> None:
        """Translate OpenAI SDK errors into CoursePilot error types."""

        if isinstance(exc, openai.AuthenticationError):
            raise AIProviderAuthenticationError(
                "OpenAI authentication failed. Check the configured API credentials."
            ) from exc

        if isinstance(exc, openai.PermissionDeniedError):
            raise AIProviderAuthenticationError(
                "OpenAI denied the request. Check the API key permissions and project access."
            ) from exc

        if isinstance(exc, openai.RateLimitError):
            error = getattr(exc, "body", None)
            if isinstance(error, dict):
                details = error.get("error", error)
                if isinstance(details, dict):
                    code = details.get("code")
                    error_type = details.get("type")
                    if code == "insufficient_quota" or error_type == "insufficient_quota":
                        raise AIProviderQuotaExceededError(
                            "OpenAI usage quota or billing limit has been reached."
                        ) from exc

            raise AIProviderRateLimitError(
                "OpenAI is receiving too many requests. Please try again shortly."
            ) from exc

        if isinstance(
            exc,
            (
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.InternalServerError,
            ),
        ):
            raise AIProviderTemporaryError(
                "OpenAI is temporarily unavailable. Please try again shortly."
            ) from exc

        if isinstance(exc, openai.APIStatusError):
            raise AIProviderUnavailableError(
                "OpenAI could not complete the request. Please try again later."
            ) from exc

        raise AIProviderUnavailableError(
            "OpenAI could not complete the request. Please try again."
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

        messages = []

        if system_instruction:
            messages.append({
                "role": "system",
                "content": system_instruction,
            })

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.responses.create(
                model=self.model,
                input=messages,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            self._raise_api_error(exc)

        text = getattr(response, "output_text", None)

        if not isinstance(text, str) or not text.strip():
            raise AIProviderResponseError(
                "OpenAI returned no usable text."
            )

        usage_data = getattr(response, "usage", None)

        incomplete_details = getattr(response, "incomplete_details", None)
        incomplete_reason = getattr(incomplete_details, "reason", None)
        response_status = getattr(response, "status", None)

        return AIResponse(
            content=text.strip(),
            provider=self.provider_name,
            model=getattr(response, "model", None) or self.model,
            usage=AIUsage(
                input_tokens=getattr(usage_data, "input_tokens", None),
                output_tokens=getattr(usage_data, "output_tokens", None),
                total_tokens=getattr(usage_data, "total_tokens", None),
            ),
            finish_reason=(
                incomplete_reason
                or response_status
            ),
            request_id=getattr(response, "_request_id", None),
            metadata={
                "response_status": response_status,
                "incomplete_reason": incomplete_reason,
            },
        )
