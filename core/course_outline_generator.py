
import json
from typing import Any

from ai_providers.exceptions import AIProviderError
from ai_providers.factory import get_ai_provider
from core.generation_parser import GenerationOutputError
from core.generation_response_checks import is_response_truncated
from core.models import AIConfiguration

MAX_OUTLINE_ATTEMPTS = 3
DEFAULT_WEEKS_PER_BATCH = 2
MAX_OUTPUT_TOKENS = 8192


class CourseOutlineGenerationError(Exception):
    """Raised when a valid course outline batch cannot be generated."""


def generate_course_outline_batch(
    data: dict[str, Any],
    *,
    start_week: int = 1,
    week_count: int = DEFAULT_WEEKS_PER_BATCH,
):
    """Generate and validate an outline for a bounded range of weeks."""
    try:
        total_weeks = int(data.get("course_weeks") or 0)
        classes_per_week = int(data.get("classes_per_week") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("The course schedule must contain integers.") from exc

    if total_weeks < 1 or classes_per_week < 1:
        raise ValueError("Course weeks and classes per week must be positive.")

    if start_week < 1 or week_count < 1:
        raise ValueError("The start week and batch size must be positive.")

    if start_week > total_weeks:
        raise ValueError("The start week exceeds the course schedule.")

    end_week = min(start_week + week_count - 1, total_weeks)
    expected_weeks = list(range(start_week, end_week + 1))
    first_session = (start_week - 1) * classes_per_week + 1
    last_session = end_week * classes_per_week

    provider_name = AIConfiguration.get_active_provider()

    try:
        provider = get_ai_provider(provider_name)
        prompt = _build_outline_prompt(
            data,
            start_week=start_week,
            end_week=end_week,
            first_session=first_session,
            last_session=last_session,
        )
    except AIProviderError as exc:
        raise CourseOutlineGenerationError(
            "The AI service is currently unavailable."
        ) from exc

    last_error = None

    for attempt in range(1, MAX_OUTLINE_ATTEMPTS + 1):
        try:
            response = provider.generate_text(
                prompt,
                system_instruction=(
                    "You are CoursePilot, an educational course designer. "
                    "Return only valid JSON without Markdown fences. "
                    "Generate an outline, not full lesson notes. "
                    "Never use the em dash character. Use regular hyphens "
                    "or appropriate punctuation instead."
                ),
                temperature=0.3,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )

            if is_response_truncated(response):
                raise GenerationOutputError(
                    "The AI response was truncated."
                )

            weeks = _parse_and_validate_outline_batch(
                response.content,
                expected_weeks=expected_weeks,
                classes_per_week=classes_per_week,
                first_session=first_session,
                last_session=last_session,
            )

            return weeks, response

        except (AIProviderError, GenerationOutputError) as exc:
            last_error = exc

    raise CourseOutlineGenerationError(
        f"Could not generate outline weeks {start_week}-{end_week} "
        f"after {MAX_OUTLINE_ATTEMPTS} attempts."
    ) from last_error


def _parse_and_validate_outline_batch(
    raw_output: str,
    *,
    expected_weeks: list[int],
    classes_per_week: int,
    first_session: int,
    last_session: int,
) -> list[dict[str, Any]]:
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise GenerationOutputError("The AI returned an empty outline.")

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise GenerationOutputError(
            "The AI outline was not valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise GenerationOutputError("The outline must be a JSON object.")

    weeks = payload.get("weeks")
    if not isinstance(weeks, list):
        raise GenerationOutputError("'weeks' must be a list.")

    if [w.get("week_number") for w in weeks if isinstance(w, dict)] != expected_weeks:
        raise GenerationOutputError(
            "The AI returned missing, extra, or incorrectly ordered weeks."
        )

    expected_session = first_session
    validated_weeks = []

    for week in weeks:
        if not isinstance(week, dict):
            raise GenerationOutputError("Each week must be an object.")

        title = week.get("title")
        goals = week.get("learning_goals", [])
        sessions = week.get("sessions")

        if not isinstance(title, str) or not title.strip():
            raise GenerationOutputError("Each week needs a title.")

        if (
            not isinstance(goals, list)
            or not all(isinstance(goal, str) and goal.strip() for goal in goals)
        ):
            raise GenerationOutputError(
                "Each week must have valid learning goals."
            )

        if not isinstance(sessions, list) or len(sessions) != classes_per_week:
            raise GenerationOutputError(
                f"Each week must contain exactly {classes_per_week} sessions."
            )

        validated_sessions = []

        for session in sessions:
            if not isinstance(session, dict):
                raise GenerationOutputError("Each session must be an object.")

            if session.get("session_number") != expected_session:
                raise GenerationOutputError(
                    "Session numbers must be consecutive across the course."
                )

            title = session.get("title")
            topic = session.get("topic")
            objectives = session.get("learning_objectives")

            if not isinstance(title, str) or not title.strip():
                raise GenerationOutputError("Each session needs a title.")

            if not isinstance(topic, str) or not topic.strip():
                raise GenerationOutputError("Each session needs a topic.")

            if (
                not isinstance(objectives, list)
                or not objectives
                or not all(
                    isinstance(obj, str) and obj.strip()
                    for obj in objectives
                )
            ):
                raise GenerationOutputError(
                    "Each session needs at least one learning objective."
                )

            validated_sessions.append({
                "session_number": expected_session,
                "title": title.strip().replace("—", "-"),
                "topic": topic.strip().replace("—", "-"),
                "learning_objectives": [
                    obj.strip().replace("—", "-") for obj in objectives
                ],
            })
            expected_session += 1

        validated_weeks.append({
            "week_number": week["week_number"],
            "title": week["title"].strip().replace("—", "-"),
            "learning_goals": [
                goal.strip().replace("—", "-") for goal in goals
            ],
            "sessions": validated_sessions,
        })

    if expected_session - 1 != last_session:
        raise GenerationOutputError(
            "The outline does not cover the expected session range."
        )

    return validated_weeks


def _build_outline_prompt(
    data: dict[str, Any],
    *,
    start_week: int,
    end_week: int,
    first_session: int,
    last_session: int,
) -> str:
    return f"""
Design a coherent course outline for CoursePilot.

COURSE DETAILS
Topic: {(data.get("topic") or "Use the supplied source material").strip()}
Learner level: {data.get("learner_level", "intermediate")}
Detail preference: {data.get("detail_level", "standard")}
Total weeks: {data["course_weeks"]}
Classes per week: {data["classes_per_week"]}
Duration per class: {data.get("class_duration_minutes", 60)} minutes

SOURCE MATERIAL
{(data.get("source_text") or "").strip() or "No source material supplied."}

REQUESTED RANGE
Generate weeks {start_week} through {end_week}, inclusive.
Each week must have exactly {data["classes_per_week"]} sessions.
Use session numbers {first_session} through {last_session}, consecutively.
Do not include weeks or sessions outside the requested range.

OUTLINE RULES
- Organize concepts from foundational to advanced.
- Make each session distinct and appropriate for the learner level.
- Give every week learning goals.
- Give every session a title, focused topic, and measurable objectives.
- Avoid repetitive sessions, vague titles, and placeholder text.
- Do not generate full lesson notes, quizzes, activities, or assignments.
- Do not use the em dash character.

OUTPUT FORMAT
Return only valid JSON:
{{
  "weeks": [
    {{
      "week_number": {start_week},
      "title": "Week title",
      "learning_goals": ["Goal 1"],
      "sessions": [
        {{
          "session_number": {first_session},
          "title": "Session title",
          "topic": "Focused topic",
          "learning_objectives": ["Measurable objective"]
        }}
      ]
    }}
  ]
}}

The example numbers are illustrative. Return every week and session
in the requested range, with no omissions.
""".strip()
