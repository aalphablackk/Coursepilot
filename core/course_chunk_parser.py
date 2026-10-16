
import json
from typing import Any
from core.generation_schemas import CourseSession, LessonSection
from core.generation_parser import (
    GenerationOutputError,
    _parse_question,
    _require_dict,
    _require_int,
    _require_list,
    _require_string,
)



def parse_course_session_batch(raw_output: str) -> list[CourseSession]:
    """
    Parse a JSON batch containing course sessions.

    Expected JSON:
    {
        "sessions": [
            {
                "session_number": 1,
                "title": "Introduction to Python",
                "topic": "Python fundamentals",
                "learning_objectives": ["Explain what Python is"],
                "content": "Detailed teaching content...",
                "activity": "A practical activity...",
                "quiz_questions": [],
                "assignment": "A short assignment...",
                "teaching_notes": "Instructor guidance..."
            }
        ]
    }
    """
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise GenerationOutputError("The AI returned an empty session batch.")

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise GenerationOutputError(
            "The AI session batch was not valid JSON."
        ) from exc

    data = _require_dict(data, "output")
    raw_sessions = _require_list(data.get("sessions"), "sessions")

    if not raw_sessions:
        raise GenerationOutputError(
            "The AI returned a session batch with no sessions."
        )

    sessions = []

    for index, value in enumerate(raw_sessions):
        path = f"sessions[{index}]"
        item = _require_dict(value, path)

        objectives = _require_list(
            item.get("learning_objectives"),
            f"{path}.learning_objectives",
        )
        quiz_questions = _require_list(
            item.get("quiz_questions", []),
            f"{path}.quiz_questions",
        )
        raw_sections = _require_list(
            item.get("sections", []),
            f"{path}.sections",
        )

        sections = []

        for section_index, raw_section in enumerate(raw_sections):
            section_path = f"{path}.sections[{section_index}]"
            section_data = _require_dict(raw_section, section_path)

            heading = _require_string(
                section_data.get("heading"),
                f"{section_path}.heading",
            )
            section_content = _require_string(
                section_data.get("content"),
                f"{section_path}.content",
            )

            if not heading.strip() or not section_content.strip():
                raise GenerationOutputError(
                    f"{section_path} must include a heading and content."
                )

            sections.append(
                LessonSection(
                    heading=heading,
                    content=section_content,
                )
            )

        session = CourseSession(
            sections=sections,
            session_number=_require_int(
                item.get("session_number"),
                f"{path}.session_number",
            ),
            title=_require_string(item.get("title"), f"{path}.title"),
            topic=_require_string(item.get("topic"), f"{path}.topic"),
            learning_objectives=[
                _require_string(objective, f"{path}.learning_objectives[{i}]")
                for i, objective in enumerate(objectives)
            ],
            content=_require_string(
                item.get("content", ""),
                f"{path}.content",
            ),
            activity=_require_string(
                item.get("activity", ""),
                f"{path}.activity",
            ),
            quiz_questions=[
                _parse_question(question, f"{path}.quiz_questions[{i}]")
                for i, question in enumerate(quiz_questions)
            ],
            assignment=_require_string(
                item.get("assignment", ""),
                f"{path}.assignment",
            ),
            teaching_notes=_require_string(
                item.get("teaching_notes", ""),
                f"{path}.teaching_notes",
            ),
        )

        if not session.title.strip() or not session.topic.strip():
            raise GenerationOutputError(
                f"{path} must have a title and topic."
            )

        if not session.learning_objectives:
            raise GenerationOutputError(
                f"{path} must include at least one learning objective."
            )

        combined_content = "\n\n".join(
            section.content for section in session.sections
        ).strip()

        if session.sections:
            if len(combined_content) < 2500:
                raise ValueError(
                    f"Session {session.session_number} has insufficient teaching content."
                )
        elif len(session.content.strip()) < 2500:
            raise ValueError(
                f"Session {session.session_number} has insufficient teaching content."
            )

        if len(session.quiz_questions) < 10:
            raise GenerationOutputError(
                f"{path} must include at least 10 quiz questions."
            )

        for question_index, question in enumerate(session.quiz_questions):
            question_path = f"{path}.quiz_questions[{question_index}]"

            if question.question_type != "multiple_choice":
                raise GenerationOutputError(
                    f"{question_path} must be a multiple-choice question."
                )

            if len(question.options) != 4:
                raise GenerationOutputError(
                    f"{question_path} must have exactly four options."
                )

            if not question.question.strip() or not question.answer.strip():
                raise GenerationOutputError(
                    f"{question_path} must include a question and answer."
                )

            if not question.explanation.strip():
                raise GenerationOutputError(
                    f"{question_path} must include an explanation."
                )

        sessions.append(session)
    return sessions