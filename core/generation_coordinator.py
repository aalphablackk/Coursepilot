
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GenerationPlan:
    """Describes how a generation request should be divided."""

    mode: str
    strategy: str
    chunk_count: int
    reason: str


# These are initial application-level thresholds, not model token limits.
DEFAULT_SOURCE_CHARS_PER_CHUNK = 8_000
DEFAULT_SINGLE_REQUEST_SOURCE_LIMIT = 8_000
FULL_COURSE_SINGLE_REQUEST_SESSION_LIMIT = 2


def build_generation_plan(data: dict[str, Any]) -> GenerationPlan:
    """
    Choose a generation strategy before calling an AI provider.

    The coordinator is provider-independent. Provider-specific output limits
    and finish reasons will be handled by the provider layer.
    """
    mode = data.get("mode", "quick_lesson")
    source_text = (data.get("source_text") or "").strip()
    source_length = len(source_text)

    if mode == "full_course":
        weeks = int(data.get("course_weeks") or 1)
        classes_per_week = int(data.get("classes_per_week") or 1)
        total_sessions = weeks * classes_per_week

        if total_sessions > FULL_COURSE_SINGLE_REQUEST_SESSION_LIMIT:
            return GenerationPlan(
                mode=mode,
                strategy="session_chunks",
                chunk_count=total_sessions,
                reason=(
                    f"Course contains {total_sessions} sessions; "
                    "generate sessions in smaller units."
                ),
            )

    if source_length > DEFAULT_SINGLE_REQUEST_SOURCE_LIMIT:
        chunk_count = (
            source_length + DEFAULT_SOURCE_CHARS_PER_CHUNK - 1
        ) // DEFAULT_SOURCE_CHARS_PER_CHUNK

        return GenerationPlan(
            mode=mode,
            strategy="source_chunks",
            chunk_count=chunk_count,
            reason=(
                f"Source contains {source_length} characters; "
                f"split it into {chunk_count} sections."
            ),
        )

    return GenerationPlan(
        mode=mode,
        strategy="single_request",
        chunk_count=1,
        reason="Request is within the initial single-request thresholds.",
    )
