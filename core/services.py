from .models import AIConfiguration

from typing import Any
from ai_providers.research import WebResearchService
from ai_providers.exceptions import AIProviderError
from ai_providers.factory import get_ai_provider

from .generation_parser import (
    GenerationOutputError,
    parse_generation_output,
)
from .generation_validation import validate_generation_output
from .prompt_builder import build_generation_prompt
import logging

logger = logging.getLogger(__name__)

class LessonGenerationError(Exception):
    """Raised when CoursePilot cannot generate valid lesson content."""



def generate_lesson(data: dict[str, Any]):
    """
    Generate, parse, and validate lesson content.

    Provider selection is explicit when supplied; otherwise the
    factory uses the configured default provider.
    """

    provider_name = AIConfiguration.get_active_provider()

    try:
        generation_data = dict(data)

        if generation_data.get("use_web_research"):
            research_topic = (
                generation_data.get("topic")
                or generation_data.get("source_text")
                or ""
            ).strip()

            if not research_topic:
                raise LessonGenerationError(
                    "A topic or source text is required for web research."
                )

            research_query = (
                f"Current, reliable educational information about: "
                f"{research_topic[:500]}. "
                "Prioritize official documentation and authoritative sources."
            )

            try:
                research_service = WebResearchService()
                research_sources = research_service.search(
                    research_query,
                    max_results=5,
                )
            except LessonGenerationError:
                raise
            except AIProviderError as exc:
                logger.exception("Web research failed.")
                raise LessonGenerationError(
                    "Web research is currently unavailable. "
                    "Please try again or turn off web research."
                ) from exc

            if not research_sources:
                raise LessonGenerationError(
                    "Web research returned no usable sources. "
                    "Please try a different topic or turn off web research."
                )

            generation_data["research_sources"] = research_sources

        provider = get_ai_provider(provider_name)
        prompt = build_generation_prompt(generation_data)

        response = provider.generate_text(
            prompt,
            system_instruction=(
                "You are CoursePilot, an educational content assistant. "
                "Follow the supplied instructions and output contract. "
                "Return only valid JSON, without Markdown code fences."
            ),
            temperature=0.4,
            max_output_tokens=8192,
        )

        logger.info(
            "AI generation response. Provider=%s Model=%s Mode=%s "
            "FinishReason=%s Status=%s InputTokens=%s OutputTokens=%s "
            "ResponseLength=%s RequestID=%s",
            response.provider,
            response.model,
            data.get("mode"),
            response.finish_reason,
            (response.metadata or {}).get("response_status"),
            response.usage.input_tokens,
            response.usage.output_tokens,
            len(response.content),
            response.request_id,
        )

        if _is_incomplete_response(response):
            logger.error(
                "AI response was incomplete. Provider=%s Model=%s "
                "Mode=%s FinishReason=%s Metadata=%s",
                response.provider,
                response.model,
                data.get("mode"),
                response.finish_reason,
                response.metadata,
            )
            raise LessonGenerationError(
                "The course was too large for a single AI response. "
                "Please try a smaller course while we improve course generation."
            )

        output = parse_generation_output(response.content)

        # CHANGED: Pass the requested duration to validation so
        # Quick Lesson and Presentation duration plans can be checked.
        validate_generation_output(
            output,
            mode=data["mode"],
            course_weeks=data.get("course_weeks"),
            classes_per_week=data.get("classes_per_week"),
            duration_minutes=data.get("duration_minutes"),
        )

        print("AI provider:", provider_name)
        print("AI response length:", len(response.content))
        print(
            "AI finish reason:",
            getattr(response, "finish_reason", "Not available"),
        )

        return output, response

    except AIProviderError as exc:
        logger.exception(
            "AI provider error. Mode=%s, Provider=%s, ErrorType=%s",
            data.get("mode"),
            provider_name,
            type(exc).__name__,
        )
        raise LessonGenerationError(
            "Our AI service is temporarily unavailable. "
            "Please try again in a few minutes."
        ) from exc

    except Exception as exc:
        logger.exception(
            "Lesson generation failed. Mode=%s, Provider=%s, "
            "ErrorType=%s, Error=%s",
            data.get("mode"),
            provider_name,
            type(exc).__name__,
            str(exc),
        )
        raise LessonGenerationError(
            "We couldn't complete your lesson right now. "
            "Please try again later."
        ) from exc

def _is_incomplete_response(response) -> bool:
    """Detect output that stopped before generation was complete."""

    finish_reason = str(
        getattr(response, "finish_reason", "") or ""
    ).upper()

    status = str(
        (getattr(response, "metadata", None) or {}).get(
            "response_status", ""
        )
    ).upper()

    return (
        finish_reason in {
            "MAX_TOKENS",
            "MAX_OUTPUT_TOKENS",
            "LENGTH",
            "INCOMPLETE",
        }
        or status == "INCOMPLETE"
    )