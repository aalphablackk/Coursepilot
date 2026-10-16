
from typing import Any


TRUNCATION_REASONS = {
    "MAX_TOKENS",
    "MAX_OUTPUT_TOKENS",
    "LENGTH",
}


def is_response_truncated(response: Any) -> bool:
    """Return True when the provider explicitly reports token-limit truncation."""
    finish_reason = _normalize_reason(
        getattr(response, "finish_reason", None)
    )

    metadata = getattr(response, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    incomplete_reason = _normalize_reason(
        metadata.get("incomplete_reason")
    )

    if finish_reason in TRUNCATION_REASONS:
        return True

    if incomplete_reason in TRUNCATION_REASONS:
        return True

    return False


def _normalize_reason(value: Any) -> str:
    """Normalize provider-specific reason values for comparison."""
    if value is None:
        return ""

    value = getattr(value, "name", value)
    return str(value).strip().upper()
