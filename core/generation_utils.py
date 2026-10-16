from typing import Any


def is_incomplete_response(response: Any) -> bool:
    """
    Detect responses that the provider explicitly reports as incomplete.

    Works with the normalized AIResponse interface and optional
    provider metadata.
    """
    finish_reason = str(
        getattr(response, "finish_reason", "") or ""
    ).upper()

    metadata = getattr(response, "metadata", None) or {}
    status = str(metadata.get("response_status", "") or "").upper()

    incomplete_reasons = {
        "MAX_TOKENS",
        "MAX_OUTPUT_TOKENS",
        "LENGTH",
        "INCOMPLETE",
    }

    return (
        finish_reason in incomplete_reasons
        or status == "INCOMPLETE"
    )


def split_text_into_chunks(
    text: str,
    *,
    max_chars: int = 8_000,
) -> list[str]:
    """
    Split long source text into manageable chunks, preferring paragraph
    boundaries and avoiding empty chunks.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero.")

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n\n", 0, max_chars + 1)

        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, max_chars + 1)

        if split_at <= 0:
            split_at = max_chars

        chunk = remaining[:split_at].strip()

        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks