
import json
from typing import Any

from core.generation_schemas import (
    CourseSession,
    CourseWeek,
    LessonActivity,
    LessonOutput,
    LessonQuestion,
    LessonSection,
    LearningObjective,
    PresentationSlide,
)


class GenerationOutputError(ValueError):
    """Raised when generated AI content is invalid."""


def _require_dict(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        raise GenerationOutputError(f"{path} must be an object.")
    return value


def _require_list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        raise GenerationOutputError(f"{path} must be a list.")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise GenerationOutputError(f"{path} must be a string.")
    return value


def _require_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GenerationOutputError(f"{path} must be an integer.")
    return value


def _parse_question(value: Any, path: str) -> LessonQuestion:
    item = _require_dict(value, path)

    options = _require_list(item.get("options", []), f"{path}.options")

    return LessonQuestion(
        question=_require_string(
            item.get("question"), f"{path}.question"
        ),
        answer=_require_string(
            item.get("answer", ""), f"{path}.answer"
        ),
        question_type=_require_string(
            item.get("question_type", "short_answer"),
            f"{path}.question_type",
        ),
        options=[
            _require_string(option, f"{path}.options[{index}]")
            for index, option in enumerate(options)
        ],
        explanation=_require_string(
            item.get("explanation", ""), f"{path}.explanation"
        ),
        hint=_require_string(
            item.get("hint", ""), f"{path}.hint"
        ),
        section_heading=_require_string(
            item.get("section_heading", ""),
            f"{path}.section_heading",
        ),
    )


def parse_generation_output(raw_output: str) -> LessonOutput:
    """Parse and validate JSON returned by an AI provider."""

    if not isinstance(raw_output, str) or not raw_output.strip():
        raise GenerationOutputError("The AI returned an empty response.")

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise GenerationOutputError(
            "The AI response was not valid JSON."
        ) from exc

    data = _require_dict(data, "output")

    required_strings = (
        "title",
        "introduction",
        "assignment",
        "conclusion",
        "teaching_notes",
    )
    for field_name in required_strings:
        if field_name not in data:
            raise GenerationOutputError(
                f"Missing required field: {field_name}."
            )
        _require_string(data[field_name], field_name)

    objectives = [
        LearningObjective(
            description=_require_string(
                _require_dict(item, f"learning_objectives[{index}]").get(
                    "description"
                ),
                f"learning_objectives[{index}].description",
            )
        )
        for index, item in enumerate(
            _require_list(data.get("learning_objectives", []),
                          "learning_objectives")
        )
    ]

    sections = []
    for index, value in enumerate(
        _require_list(data.get("sections", []), "sections")
    ):
        item = _require_dict(value, f"sections[{index}]")
        sections.append(
            LessonSection(
                heading=_require_string(
                    item.get("heading"), f"sections[{index}].heading"
                ),
                content=_require_string(
                    item.get("content"), f"sections[{index}].content"
                ),
            )
        )

    questions = [
        _parse_question(item, f"questions[{index}]")
        for index, item in enumerate(
            _require_list(data.get("questions", []), "questions")
        )
    ]

    activities = []
    for index, value in enumerate(
        _require_list(data.get("activities", []), "activities")
    ):
        item = _require_dict(value, f"activities[{index}]")
        activities.append(
            LessonActivity(
                title=_require_string(
                    item.get("title"), f"activities[{index}].title"
                ),
                instructions=_require_string(
                    item.get("instructions"),
                    f"activities[{index}].instructions",
                ),
                activity_type=_require_string(
                    item.get("activity_type", "class_activity"),
                    f"activities[{index}].activity_type",
                ),
            )
        )

    slides = []
    for index, value in enumerate(
        _require_list(
            data.get("presentation_slides", []), "presentation_slides"
        )
    ):
        item = _require_dict(value, f"presentation_slides[{index}]")
        bullets = _require_list(
            item.get("bullet_points", []),
            f"presentation_slides[{index}].bullet_points",
        )
        slides.append(
            PresentationSlide(
                title=_require_string(
                    item.get("title"),
                    f"presentation_slides[{index}].title",
                ),
                bullet_points=[
                    _require_string(
                        bullet,
                        f"presentation_slides[{index}].bullet_points[{bullet_index}]",
                    )
                    for bullet_index, bullet in enumerate(bullets)
                ],
                speaker_notes=_require_string(
                    item.get("speaker_notes", ""),
                    f"presentation_slides[{index}].speaker_notes",
                ),
            )
        )

    course_weeks = []
    for week_index, week_value in enumerate(
        _require_list(data.get("course_weeks", []), "course_weeks")
    ):
        week = _require_dict(week_value, f"course_weeks[{week_index}]")

        sessions = []
        for session_index, session_value in enumerate(
            _require_list(
                week.get("sessions", []),
                f"course_weeks[{week_index}].sessions",
            )
        ):
            session = _require_dict(
                session_value,
                f"course_weeks[{week_index}].sessions[{session_index}]",
            )
            session_path = (
                f"course_weeks[{week_index}].sessions[{session_index}]"
            )

            objectives_list = _require_list(
                session.get("learning_objectives", []),
                f"{session_path}.learning_objectives",
            )
            quiz_list = _require_list(
                session.get("quiz_questions", []),
                f"{session_path}.quiz_questions",
            )

            sessions.append(
                CourseSession(
                    session_number=_require_int(
                        session.get("session_number"),
                        f"{session_path}.session_number",
                    ),
                    title=_require_string(
                        session.get("title"), f"{session_path}.title"
                    ),
                    topic=_require_string(
                        session.get("topic"), f"{session_path}.topic"
                    ),
                    learning_objectives=[
                        _require_string(
                            objective,
                            f"{session_path}.learning_objectives[{i}]",
                        )
                        for i, objective in enumerate(objectives_list)
                    ],
                    content=_require_string(
                        session.get("content", ""),
                        f"{session_path}.content",
                    ),
                    activity=_require_string(
                        session.get("activity", ""),
                        f"{session_path}.activity",
                    ),
                    quiz_questions=[
                        _parse_question(item, f"{session_path}.quiz_questions[{i}]")
                        for i, item in enumerate(quiz_list)
                    ],
                    assignment=_require_string(
                        session.get("assignment", ""),
                        f"{session_path}.assignment",
                    ),
                    teaching_notes=_require_string(
                        session.get("teaching_notes", ""),
                        f"{session_path}.teaching_notes",
                    ),
                )
            )

        goals = _require_list(
            week.get("learning_goals", []),
            f"course_weeks[{week_index}].learning_goals",
        )

        course_weeks.append(
            CourseWeek(
                week_number=_require_int(
                    week.get("week_number"),
                    f"course_weeks[{week_index}].week_number",
                ),
                title=_require_string(
                    week.get("title"), f"course_weeks[{week_index}].title"
                ),
                learning_goals=[
                    _require_string(goal, f"course_weeks[{week_index}].learning_goals[{i}]")
                    for i, goal in enumerate(goals)
                ],
                sessions=sessions,
            )
        )

    def parse_string_list(field_name: str) -> list[str]:
        values = _require_list(data.get(field_name, []), field_name)
        return [
            _require_string(value, f"{field_name}[{index}]")
            for index, value in enumerate(values)
        ]

    sources = _require_list(data.get("sources", []), "sources")
    metadata = _require_dict(data.get("metadata", {}), "metadata")

    return LessonOutput(
        title=data["title"],
        introduction=data["introduction"],
        learning_objectives=objectives,
        sections=sections,
        key_points=parse_string_list("key_points"),
        examples=parse_string_list("examples"),
        fun_facts=parse_string_list("fun_facts"),
        questions=questions,
        activities=activities,
        assignment=data["assignment"],
        conclusion=data["conclusion"],
        teaching_notes=data["teaching_notes"],
        presentation_slides=slides,
        course_weeks=course_weeks,
        sources=[
            _require_dict(source, f"sources[{index}]")
            for index, source in enumerate(sources)
        ],
        metadata=metadata,
    )
