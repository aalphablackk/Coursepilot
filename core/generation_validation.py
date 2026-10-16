
from core.generation_parser import GenerationOutputError
from core.generation_schemas import LessonOutput


def validate_generation_output(
    output: LessonOutput,
    *,
    mode: str,
    course_weeks: int | None = None,
    classes_per_week: int | None = None,
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

    elif mode == "summary":
        if not output.sections:
            raise GenerationOutputError(
                "A structured summary must include sections."
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

    elif mode == "custom_content":
        if not output.sections and not output.introduction.strip():
            raise GenerationOutputError(
                "Custom content must contain organized content."
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

                expected_session_number += 1

    else:
        raise GenerationOutputError(
            f"Unsupported generation mode: {mode}"
        )

    return output
