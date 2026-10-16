
from typing import Any

from ai_providers.exceptions import AIProviderError
from ai_providers.factory import get_ai_provider
from core.course_chunk_parser import parse_course_session_batch
from core.generation_parser import GenerationOutputError
from core.generation_response_checks import is_response_truncated
from core.models import AIConfiguration

MAX_BATCH_ATTEMPTS = 3
DEFAULT_SESSIONS_PER_BATCH = 2
MAX_OUTPUT_TOKENS = 8192


class CourseChunkGenerationError(Exception):
    """Raised when a course session batch cannot be generated."""


def generate_course_session_batch(
    data: dict[str, Any],
    *,
    start_session: int,
    session_count: int = DEFAULT_SESSIONS_PER_BATCH,
):
    if start_session < 1:
        raise ValueError("start_session must be at least 1.")

    if session_count < 1:
        raise ValueError("session_count must be at least 1.")

    total_weeks = int(data.get("course_weeks") or 1)
    classes_per_week = int(data.get("classes_per_week") or 1)
    total_sessions = total_weeks * classes_per_week

    if start_session > total_sessions:
        raise ValueError("start_session exceeds the course schedule.")

    end_session = min(
        start_session + session_count - 1,
        total_sessions,
    )
    expected_numbers = list(range(start_session, end_session + 1))

    provider_name = AIConfiguration.get_active_provider()

    try:
        provider = get_ai_provider(provider_name)

        prompt = _build_session_batch_prompt(
            data,
            start_session=start_session,
            end_session=end_session,
            total_sessions=total_sessions,
        )

        last_error = None

        for attempt in range(1, MAX_BATCH_ATTEMPTS + 1):
            try:
                response = provider.generate_text(
                    prompt,
                    system_instruction=(
                        "You are CoursePilot, an educational content assistant. "
                        "Follow the requested session range and output contract. "
                        "Return only valid JSON, without Markdown code fences. "
                        "Never use the em dash character. Use commas, colons, "
                        "semicolons, or regular hyphens instead."
                    ),
                    temperature=0.4,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                )

                if is_response_truncated(response):
                    raise GenerationOutputError(
                        "The AI response reached its output token limit."
                    )

                sessions = parse_course_session_batch(response.content)

                actual_numbers = [
                    session.session_number for session in sessions
                ]

                if actual_numbers != expected_numbers:
                    raise GenerationOutputError(
                        "The AI returned sessions outside the requested "
                        "range or in the wrong order."
                    )

                return sessions, response

            except (AIProviderError, GenerationOutputError) as exc:
                last_error = exc

                if attempt < MAX_BATCH_ATTEMPTS:
                    continue

        raise CourseChunkGenerationError(
            f"Could not generate course sessions "
            f"{start_session}-{end_session} after "
            f"{MAX_BATCH_ATTEMPTS} attempts."
        ) from last_error

    except AIProviderError as exc:
        raise CourseChunkGenerationError(
            f"Could not generate course sessions "
            f"{start_session}-{end_session}."
        ) from exc


def _build_session_batch_prompt(
    data: dict[str, Any],
    *,
    start_session: int,
    end_session: int,
    total_sessions: int,
) -> str:
    topic = (data.get("topic") or "").strip()
    source_text = (data.get("source_text") or "").strip()
    learner_level = data.get("learner_level", "beginner")
    detail_level = data.get("detail_level", "standard")
    total_weeks = int(data.get("course_weeks") or 1)
    classes_per_week = int(data.get("classes_per_week") or 1)
    duration = data.get("duration_minutes", 60)

    outline = data.get("session_outline") or {}
    outline_title = (outline.get("title") or "").strip()
    outline_topic = (outline.get("topic") or "").strip()
    outline_objectives = outline.get("learning_objectives") or []

    if not isinstance(outline_objectives, list):
        outline_objectives = []

    objectives_text = (
        "\n".join(f"- {objective}" for objective in outline_objectives)
        or "- Use appropriate measurable learning objectives."
    )

    if outline_title or outline_topic or outline_objectives:
        outline_instructions = f"""
REVIEWED COURSE OUTLINE
Session number: {start_session}
Reviewed session title: {outline_title or "Use the planned session title"}
Reviewed topic: {outline_topic or "Use the planned session topic"}

Reviewed learning objectives:
{objectives_text}

IMPORTANT OUTLINE RULES
- Treat the reviewed outline as the source of truth for this session.
- Preserve the reviewed title and topic.
- Address every reviewed learning objective.
- You may expand the objectives into clear explanations, examples,
  activities, questions, assignments, and instructor notes.
- Do not replace the planned session with a different topic.
- Keep the content consistent with the overall course sequence.
""".strip()
    else:
        outline_instructions = """
REVIEWED COURSE OUTLINE
No individual session outline was supplied. Generate content that fits
the requested session number and the overall course sequence.
""".strip()

    return f"""
Create an instructor-ready course session batch for CoursePilot.

COURSE DETAILS
Course topic: {topic or "Use the supplied source material"}
Learner level: {learner_level}
Detail level: {detail_level}
Course duration: {total_weeks} weeks
Classes per week: {classes_per_week}
Total sessions: {total_sessions}
Duration per session: {duration} minutes

SOURCE MATERIAL
{source_text or "No additional source material was supplied."}

{outline_instructions}

SESSION RANGE
Generate exactly sessions {start_session} through {end_session}, inclusive.
Return them in ascending session_number order.
Do not include sessions outside this range.

CONTENT REQUIREMENTS
- Respect the requested duration of {duration} minutes. Generate enough
  substantive teaching material to support the entire session, not a brief
  summary.
- For a 120-minute session, provide a structured lesson plan with timed
  segments whose durations add up to 120 minutes.
- Include a clear introduction, prerequisites, measurable learning objectives,
  and a logical sequence of teaching sections.
- Each major concept must include a detailed explanation, why it matters,
  a relevant example, and common beginner mistakes where appropriate.
- For programming topics, include runnable code examples, explain the code
  line by line, show expected output, and include practical coding exercises.
- Include guided practice, independent practice, discussion or reflection,
  a recap, and an after-class assignment.
- Include at least 8 substantial teaching sections for a 120-minute session.
  Each section must teach a distinct part of the topic.
- Include at least 10 multiple-choice quiz questions per session.
- Every quiz question must have exactly four answer options, one correct
  answer, and a meaningful explanation of why the answer is correct.
- Set question_type to "multiple_choice" for every quiz question.
- The answer must clearly identify the correct option and its answer text.
- Questions must assess the actual lesson content, not unrelated facts.
- Include useful instructor teaching notes with timing, demonstrations,
  expected learner difficulties, and guidance for activities.
- Do not use placeholders, superficial explanations, or repetitive filler.
- Do not use the em dash character(—). Use commas, colons, semicolons,
  or regular hyphens instead.
- Return teaching material in the "sections" array.
- Each section must contain a "heading" and detailed "content".
- Give each major teaching topic its own section.
- Never place formal quiz questions, options, answers, hints, or quiz
  explanations inside section content.
- Store all formal assessment questions exclusively in "quiz_questions".
- Do not duplicate questions between sections and quiz_questions.
- Do not create a separate Quiz section in the sections array.
- Keep practical activities in "activity" and assignments in "assignment".
- Ensure the combined sections contain enough detail for the requested
  session duration.

OUTPUT CONTRACT
Return only a valid JSON object with this structure:
{{
  "sessions": [
    {{
      "session_number": 1,
      "title": "Session title",
      "topic": "Session topic",
      "learning_objectives": ["Objective 1"],
      
      "sections": [
        {{
          "heading": "Introduction",
          "content": "Detailed teaching content for this section"
        }}
      ],

      "activity": "Practical classroom activity",
      "quiz_questions": [
        {{
            "question": "Which statement correctly describes the concept?",
            "answer": "B. Correct answer text",
            "question_type": "multiple_choice",
            "options": [
                "A. First possible answer",
                "B. Correct answer text",
                "C. Third possible answer",
                "D. Fourth possible answer"
            ],
            "explanation": "Explain why option B is correct.",
            "hint": "Give a clue without revealing the answer.",
            "section_heading": "Relevant lesson section"
        }}
      ],
      "assignment": "After-class assignment",
      "teaching_notes": "Instructor guidance"
    }}
  ]
}}

The example session_number is illustrative. Use the exact session numbers
requested in the SESSION RANGE. Return exactly
{end_session - start_session + 1} sessions.
""".strip()
