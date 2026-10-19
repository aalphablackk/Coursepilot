
from core.generation_parser import GenerationOutputError
from core.generation_schemas import LessonOutput


import re

from core.generation_parser import GenerationOutputError
from core.generation_schemas import LessonOutput


PLACEHOLDER_PATTERNS = [
    r"\b(add|insert|write|provide|include)\s+"
    r"(a|an|some|relevant|appropriate|detailed)?\s*"
    r"(example|explanation|content|details|information)\s+here\b",
    r"\b(to be completed|coming soon|lorem ipsum)\b",
    r"\b(insert|enter|replace)\s+"
    r"(text|content|example|answer)\s+here\b",
]

INSTRUCTION_ONLY_PATTERNS = [
    r"^(discuss|explain|introduce|describe|outline)\s+"
    r"(the following|this topic|the concept|the importance of)\b",
    r"^(students|learners|the instructor|the teacher)\s+"
    r"(should|will need to)\s+(learn about|discuss|explain)\b",
    r"^(provide|give|include|add)\s+"
    r"(examples|details|an explanation|more information)\b",
]
def validate_duration_plan(
    output: LessonOutput,
    duration_minutes: int,
) -> None:
    """Validate the structured instructor duration plan."""
    metadata = output.metadata or {}
    plan = output.metadata.get("duration_plan")

    if not isinstance(plan, dict):
        raise GenerationOutputError(
            "Generated content must include a structured duration plan."
        )

    total_minutes = plan.get("total_minutes")
    stages = plan.get("stages")

    if (
        isinstance(total_minutes, bool)
        or not isinstance(total_minutes, int)
        or total_minutes != duration_minutes
    ):
        raise GenerationOutputError(
            "Duration plan total must match the requested session duration."
        )

    if not isinstance(stages, list) or not stages:
        raise GenerationOutputError(
            "Duration plan must include at least one stage."
        )

    allocated_minutes = 0

    for index, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict):
            raise GenerationOutputError(
                f"Duration plan stage {index} must be an object."
            )

        name = stage.get("name")
        minutes = stage.get("minutes")

        if not isinstance(name, str) or not name.strip():
            raise GenerationOutputError(
                f"Duration plan stage {index} must have a name."
            )

        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or minutes <= 0
        ):
            raise GenerationOutputError(
                f"Duration plan stage {index} must have positive integer minutes."
            )

        allocated_minutes += minutes

    if allocated_minutes != duration_minutes:
        raise GenerationOutputError(
            "Duration plan stage allocations must add up to "
            "the requested session duration."
        )

def validate_substantive_text(
    value: str,
    *,
    field_name: str,
    allow_instructions: bool = False,
    min_length: int = 30,
) -> None:
    """Reject empty, placeholder, or instruction-only content."""

    text = (value or "").strip()

    if len(text) < min_length:
        raise GenerationOutputError(
            f"{field_name} is too short to contain useful content."
        )

    normalized = re.sub(r"\s+", " ", text).strip().lower()

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            raise GenerationOutputError(
                f"{field_name} contains placeholder text."
            )

    if not allow_instructions:
        for pattern in INSTRUCTION_ONLY_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                raise GenerationOutputError(
                    f"{field_name} appears to contain instructions "
                    "instead of actual educational content."
                )

def validate_generation_output(
    output: LessonOutput,
    *,
    mode: str,
    course_weeks: int | None = None,
    classes_per_week: int | None = None,
    duration_minutes: int | None = None,
) -> LessonOutput:
    """Validate that generated content meets mode-specific requirements."""

    if not isinstance(output, LessonOutput):
        raise GenerationOutputError(
            "Expected a parsed LessonOutput instance."
        )

    if not output.title.strip():
        raise GenerationOutputError("Generated content must have a title.")

    if mode == "quick_lesson":
        if not output.learning_objectives:
            raise GenerationOutputError(
                "A quick lesson must include learning objectives."
            )
        if not output.sections:
            raise GenerationOutputError(
                "A quick lesson must include lesson sections."
            )

        for index, section in enumerate(output.sections, start=1):
            validate_substantive_text(
                section.heading,
                field_name=f"Lesson section {index} heading",
                min_length=3,
            )
            validate_substantive_text(
                section.content,
                field_name=f"Lesson section {index} content",
            )


    elif mode == "summary":
        if not output.sections:
            raise GenerationOutputError(
                "A structured summary must include sections."
            )
        for index, section in enumerate(output.sections, start=1):
            validate_substantive_text(
                section.heading,
                field_name=f"Summary section {index} heading",
                min_length=3,
            )

            validate_substantive_text(
                section.content,
                field_name=f"Summary section {index} content",
            )


    elif mode == "presentation":
        if not output.presentation_slides:
            raise GenerationOutputError(
                "Presentation notes must include slides."
            )

        for index, slide in enumerate(output.presentation_slides, start=1):
            if not slide.title.strip():
                raise GenerationOutputError(
                    f"Slide {index} must have a title."
                )

            if len(slide.bullet_points) < 2:
                raise GenerationOutputError(
                    f"Slide {index} must contain at least "
                    "two substantive bullet points."
                )
            if not slide.speaker_notes.strip():
                raise GenerationOutputError(
                    f"Slide {index} must include speaker notes."
                )
            for bullet_index, bullet in enumerate(
                slide.bullet_points, start=1
            ):
                validate_substantive_text(
                    bullet,
                    field_name=(
                        f"Slide {index}, bullet {bullet_index}"
                    ),
                    min_length=15,
                )


    elif mode == "custom_content":
        if not output.sections and not output.introduction.strip():
            raise GenerationOutputError(
                "Custom content must contain organized content."
            )

        for index, section in enumerate(output.sections, start=1):
            validate_substantive_text(
                section.heading,
                field_name=f"Custom content section {index} heading",
                min_length=3,
            )

            validate_substantive_text(
                section.content,
                field_name=f"Custom content section {index} content",
            )

    elif mode == "full_course":
        if course_weeks is None or classes_per_week is None:
            raise GenerationOutputError(
                "Expected course duration and weekly class count."
            )

        if course_weeks < 1 or classes_per_week < 1:
            raise GenerationOutputError(
                "Course schedule values must be positive."
            )

        if len(output.course_weeks) != course_weeks:
            raise GenerationOutputError(
                f"Expected {course_weeks} course weeks, "
                f"but received {len(output.course_weeks)}."
            )

        expected_sessions = course_weeks * classes_per_week
        actual_sessions = sum(
            len(week.sessions) for week in output.course_weeks
        )

        if actual_sessions != expected_sessions:
            raise GenerationOutputError(
                f"Expected {expected_sessions} sessions, "
                f"but received {actual_sessions}."
            )

        expected_session_number = 1

        for week_index, week in enumerate(output.course_weeks, start=1):
            if week.week_number != week_index:
                raise GenerationOutputError(
                    "Course weeks must be numbered consecutively "
                    "starting from 1."
                )

            if len(week.sessions) != classes_per_week:
                raise GenerationOutputError(
                    f"Week {week.week_number} must contain "
                    f"{classes_per_week} sessions."
                )

            for session in week.sessions:
                if session.session_number != expected_session_number:
                    raise GenerationOutputError(
                        "Course sessions must be numbered consecutively "
                        "across the entire course."
                    )

                if not session.title.strip() or not session.topic.strip():
                    raise GenerationOutputError(
                        f"Session {expected_session_number} must have "
                        "a title and topic."
                    )

                if not session.learning_objectives:
                    raise GenerationOutputError(
                        f"Session {expected_session_number} must include "
                        "learning objectives."
                    )
                # Validate the session's actual teaching content.
                if session.content.strip():
                    validate_substantive_text(
                        session.content,
                        field_name=(
                            f"Session {expected_session_number} content"
                        ),
                    )

                if not session.content.strip() and not session.sections:
                    raise GenerationOutputError(
                        f"Session {expected_session_number} must include "
                        "teaching content or lesson sections."
                    )

                # Validate individual lesson sections.
                for section_index, section in enumerate(
                    session.sections, start=1
                ):
                    validate_substantive_text(
                        section.heading,
                        field_name=(
                            f"Session {expected_session_number}, "
                            f"section {section_index} heading"
                        ),
                        min_length=3,
                    )

                    validate_substantive_text(
                        section.content,
                        field_name=(
                            f"Session {expected_session_number}, "
                            f"section {section_index} content"
                        ),
                    )
                # Validate the session activity when one is provided.
                if session.activity.strip():
                    validate_substantive_text(
                        session.activity,
                        field_name=(
                            f"Session {expected_session_number} activity"
                        ),
                    )

                # Validate quiz questions and their answers when provided.
                for question_index, question in enumerate(
                    session.quiz_questions, start=1
                ):
                    validate_substantive_text(
                        question.question,
                        field_name=(
                            f"Session {expected_session_number}, "
                            f"quiz question {question_index}"
                        ),
                        min_length=10,
                    )

                    if question.answer.strip():
                        validate_substantive_text(
                            question.answer,
                            field_name=(
                                f"Session {expected_session_number}, "
                                f"quiz answer {question_index}"
                            ),
                        )

                # Validate the assignment when one is provided.
                if session.assignment.strip():
                    validate_substantive_text(
                        session.assignment,
                        field_name=(
                            f"Session {expected_session_number} assignment"
                        ),
                    )
                for objective_index, objective in enumerate(
                    session.learning_objectives, start=1
                ):
                    validate_substantive_text(
                        objective,
                        field_name=(
                            f"Session {expected_session_number}, "
                            f"learning objective {objective_index}"
                        ),
                        min_length=15,
                    )

                expected_session_number += 1


    else:
        raise GenerationOutputError(
            f"Unsupported generation mode: {mode}"
        )
    if (
        duration_minutes is not None
        and mode in {"quick_lesson", "presentation"}
    ):
        validate_duration_plan(output, duration_minutes)

    return output
