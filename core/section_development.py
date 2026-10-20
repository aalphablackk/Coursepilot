"""AI-assisted development of an existing CoursePilot lesson section."""

import logging

from .models import AIConfiguration
from ai_providers.exceptions import AIProviderError
from ai_providers.factory import get_ai_provider

logger = logging.getLogger(__name__)

import re


def markdown_to_plain_text(content: str) -> str:
    """Remove common Markdown formatting while preserving structure."""
    if not content:
        return ""

    text = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove fenced code block markers but preserve code.
    text = re.sub(r"(?m)^\s*```[^\n]*\n?", "", text)

    # Remove heading markers.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)

    # Convert Markdown links to visible text.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove bold, italic, and strikethrough markers.
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)

    # Remove inline code markers.
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Convert Markdown list markers to plain text.
    text = re.sub(r"(?m)^\s*[-*+]\s+", "• ", text)
    text = re.sub(r"(?m)^(\s*)\d+[.)]\s+", r"\1", text)

    # Remove blockquote markers.
    text = re.sub(r"(?m)^\s*>\s?", "", text)

    # Remove horizontal rules.
    text = re.sub(r"(?m)^\s*([-*_])(?:\s*\1){2,}\s*$", "", text)

    # Normalize excessive blank lines.
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

class SectionDevelopmentError(Exception):
    """Raised when an existing lesson section cannot be developed."""


def develop_section_content(
    *,
    heading: str,
    existing_content: str,
    lesson_title: str = "",
    lesson_topic: str = "",
    learner_level: str = "",
    learning_notes: str = "",
    neighboring_headings: list[str] | None = None,
) -> str:
    """
    Improve one existing lesson section without saving it.

    The returned text is a draft. The instructor must review and
    explicitly save it through the existing lesson editor.
    """
    heading = heading.strip() if isinstance(heading, str) else ""
    existing_content = (
        existing_content.strip()
        if isinstance(existing_content, str)
        else ""
    )

    if not heading or not existing_content:
        raise SectionDevelopmentError(
            "A section heading and existing content are required."
        )

    neighboring_headings = neighboring_headings or []

    context_lines = [
        f"Lesson title: {lesson_title or 'Not provided'}",
        f"Lesson topic: {lesson_topic or 'Not provided'}",
        f"Learner level: {learner_level or 'Not specified'}",
        f"Section heading: {heading}",
        (
            "Other section headings: "
            + (
                "; ".join(
                    str(value)
                    for value in neighboring_headings
                    if value
                )
                or "Not provided"
            )
        ),
        (
            "Learning notes/context: "
            + (learning_notes[:6000] or "Not provided")
        ),
        (
            "EXISTING SECTION CONTENT (preserve and build on this):\n"
            + existing_content[:18000]
        ),
    ]

        
    prompt = (
        "You are CoursePilot, an expert instructional editor.\n\n"

        "TASK:\n"
        "Improve and develop the existing lesson section so it is clear, "
        "well-structured, sufficiently detailed, and suitable for independent "
        "self-study. Build upon the existing content rather than merely "
        "rewriting or summarizing it.\n\n"

        "PRESERVE AND DEVELOP EXISTING CONTENT:\n"
        "- Preserve the original context, meaning, key facts, relevant "
        "terminology, useful examples, code, and learning objectives.\n"
        "- Always look for opportunities to develop the existing explanation "
        "further by adding useful information, clarification, examples, "
        "and practical applications.\n"
        "- Do not remove valuable information simply to make the content "
        "shorter or more concise.\n"
        "- Expand brief or underdeveloped content with essential explanations, "
        "additional relevant examples, and missing context needed to understand "
        "the topic independently.\n"
        "- For moderately detailed content, preserve its substance and add "
        "useful explanations, examples, and details that deepen understanding.\n"
        "- For comprehensive content, retain its depth while improving clarity, "
        "organization, completeness, and flow. Add information only where "
        "it provides meaningful educational value.\n"
        "- Remove repetition, filler, and redundant explanations when necessary, "
        "but retain all important learning information.\n\n"

        "LEARNING AND EXPLANATION REQUIREMENTS:\n"
        "- Make the content understandable without requiring an instructor "
        "to explain every point.\n"
        "- Explain important concepts clearly, including how and why they work "
        "when this helps the learner understand the subject.\n"
        "- Define unfamiliar terms when necessary.\n"
        "- Retain useful examples and code, and add more examples when they "
        "meaningfully improve understanding.\n"
        "- Use practical, real-world, worked, or code examples where appropriate "
        "to the subject.\n"
        "- Explain complex ideas progressively, moving from foundational "
        "concepts to more advanced ideas in a logical sequence.\n"
        "- Include relevant steps, comparisons, applications, and connections "
        "between concepts when they improve understanding.\n"
        "- Match the learner's level and the difficulty of the original content.\n"
        "- Ensure every addition supports the existing topic and learning "
        "objectives. Do not introduce unrelated topics or unsupported claims.\n\n"

        "BALANCE AND DETAIL:\n"
        "- Prioritize meaningful development over summarization.\n"
        "- Do not expand content merely to increase its length. Every addition "
        "must improve understanding or provide useful learning value.\n"
        "- Do not shorten content merely for the sake of brevity.\n"
        "- Make the lesson as detailed as necessary for effective self-study "
        "while avoiding unnecessary repetition and excessive explanations.\n"
        "- When the original content is already well-developed, make targeted "
        "improvements without rewriting or expanding it unnecessarily.\n\n"

        "OUTPUT RULES:\n"
        "- Return only the improved lesson section.\n"
        "- Return plain text only, without Markdown formatting, tables, "
        "or editorial commentary.\n"
        "- Use simple headings when helpful and keep paragraphs readable.\n"
        "- Never use em dashes (—). Use commas, colons, semicolons, "
        "or parentheses instead.\n"
        "- Preserve the original context and relevant terminology throughout.\n"
        "- Do not include an introduction or conclusion unless it belongs "
        "naturally in the lesson itself.\n\n"

        "CONTEXT:\n"
        + "\n\n".join(context_lines)
    )


    try:
        provider_name = AIConfiguration.get_active_provider()
        provider = get_ai_provider(provider_name)

        response = provider.generate_text(
            prompt,
            
            system_instruction=(
                "You are CoursePilot's expert adaptive lesson editor. "
                "Your goal is to develop and improve existing lesson content, not merely "
                "paraphrase or summarize it. Always preserve the original context, meaning, "
                "key facts, relevant terminology, useful examples, code, and learning objectives. "

                "Evaluate the existing content before editing. If it is brief or "
                "underdeveloped, expand it with clear explanations, relevant details, "
                "additional examples, practical applications, and missing context needed "
                "for independent learning. If it is moderately detailed, preserve its "
                "substance while adding useful depth and clarification. If it is already "
                "comprehensive, retain its depth and improve clarity, organization, and "
                "completeness without unnecessary expansion. "

                "Always look for meaningful opportunities to improve understanding. "
                "Explain important concepts, define unfamiliar terms when necessary, "
                "clarify how and why things work, and add relevant examples when they "
                "help learners understand or apply the material. Progress logically from "
                "foundational ideas to more advanced concepts, appropriate to the learner's "
                "level. Make the lesson understandable without requiring an instructor "
                "to explain every point. "

                "Do not remove valuable information simply to make the content shorter. "
                "When editing lengthy content, remove repetition, filler, and redundant "
                "explanations while preserving essential information and educational depth. "
                "Do not expand content merely to increase its length. Every addition must "
                "provide meaningful learning value and remain relevant to the original topic. "
                "Never introduce unrelated topics or unsupported claims. "

                "Return only the improved lesson section as plain text, without Markdown "
                "formatting, tables, or editorial commentary. Use simple headings when "
                "helpful. Keep paragraphs readable and explanations clear, detailed, "
                "and concise without sacrificing understanding. "

                "Never use em dashes in generated content. Use commas, colons, semicolons, "
                "or parentheses instead."
            ),

            temperature=0.35,
            max_output_tokens=5000,
        )

    except AIProviderError as exc:
        logger.exception(
            "AI provider failed while developing a lesson section."
        )
        raise SectionDevelopmentError(
            "The AI service is temporarily unavailable. "
            "Your original section is unchanged. Please try again."
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected error while developing a lesson section."
        )
        raise SectionDevelopmentError(
            "We couldn't develop this section right now. "
            "Your original section is unchanged."
        ) from exc

    finish_reason = str(
        getattr(response, "finish_reason", "") or ""
    ).upper()

    metadata = getattr(response, "metadata", None) or {}
    status = str(
        metadata.get("response_status", "")
    ).upper()

    if (
        finish_reason
        in {
            "MAX_TOKENS",
            "MAX_OUTPUT_TOKENS",
            "LENGTH",
            "INCOMPLETE",
        }
        or status == "INCOMPLETE"
    ):
        raise SectionDevelopmentError(
            "The improved section was too long for one response. "
            "Try developing a shorter section."
        )

    result = getattr(response, "content", "")

    if not isinstance(result, str) or not result.strip():
        raise SectionDevelopmentError(
            "The AI returned an empty draft. Your original section "
            "is unchanged. Please try again."
        )

    result = result.replace("—", ",")
    return markdown_to_plain_text(result.strip())