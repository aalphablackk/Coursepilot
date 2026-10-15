
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIUsage:
    """Token usage reported by an AI provider, when available."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AIResponse:
    """Normalized response shared by all AI providers."""

    content: str
    provider: str
    model: str
    usage: AIUsage = field(default_factory=AIUsage)
    finish_reason: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
