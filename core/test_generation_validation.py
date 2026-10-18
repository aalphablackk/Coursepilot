
from django.test import SimpleTestCase

from core.generation_parser import GenerationOutputError
from core.generation_schemas import (
    CourseSession,
    CourseWeek,
    LessonOutput,
    LessonSection,
    LearningObjective,
    PresentationSlide,
)
from core.generation_validation import validate_generation_output


class GenerationValidationTests(SimpleTestCase):
    def test_quick_lesson_requires_objectives(self):
        output = LessonOutput(
            title="Python",
            sections=[
                LessonSection(
                    "Introduction",
                    "Python is a programming language.",
                )
            ],
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
            )

    def test_presentation_requires_slides(self):
        output = LessonOutput(title="Networking")

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="presentation",
            )

    def test_valid_presentation_is_accepted(self):
        output = LessonOutput(
            title="Networking",
            presentation_slides=[
                PresentationSlide(
                    title="Introduction",
                    bullet_points=[
                        (
                            "A computer network connects devices "
                            "so they can communicate and share resources."
                        ),
                        (
                            "Networks use communication protocols "
                            "to define how devices exchange information."
                        ),
                    ],
                    speaker_notes=(
                        "Introduce computer networks and explain "
                        "how connected devices communicate."
                    ),
                )
            ],
        )

        result = validate_generation_output(
            output,
            mode="presentation",
        )

        self.assertIs(result, output)

    def test_full_course_rejects_missing_sessions(self):
        output = LessonOutput(
            title="Python",
            course_weeks=[
                CourseWeek(
                    week_number=1,
                    title="Foundations",
                    sessions=[
                        CourseSession(
                            session_number=1,
                            title="Introduction",
                            topic="Python basics",
                            learning_objectives=[
                                "Explain the purpose of Python."
                            ],
                            content=(
                                "Python is a programming language "
                                "used to build applications, automate "
                                "tasks, and analyze data."
                            ),
                        )
                    ],
                )
            ],
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="full_course",
                course_weeks=2,
                classes_per_week=2,
            )

    def test_full_course_accepts_complete_schedule(self):
        weeks = []

        for week_number in range(1, 3):
            sessions = []

            for class_number in range(1, 3):
                session_number = (
                    (week_number - 1) * 2 + class_number
                )

                sessions.append(
                    CourseSession(
                        session_number=session_number,
                        title=f"Class {session_number}",
                        topic=f"Topic {session_number}",
                        learning_objectives=[
                            (
                                f"Explain the main concepts of "
                                f"topic {session_number}."
                            )
                        ],
                        content=(
                            f"Topic {session_number} introduces "
                            "important concepts and explains how "
                            "they are used in practical situations. "
                            "Learners examine the underlying ideas "
                            "and how these ideas relate to the topic."
                        ),
                        sections=[
                            LessonSection(
                                heading=f"Understanding topic {session_number}",
                                content=(
                                    f"Topic {session_number} can be "
                                    "understood by examining its "
                                    "main principles and practical "
                                    "applications. These principles "
                                    "help learners understand how "
                                    "the topic works."
                                ),
                            )
                        ],
                    )
                )

            weeks.append(
                CourseWeek(
                    week_number=week_number,
                    title=f"Week {week_number}",
                    sessions=sessions,
                )
            )

        output = LessonOutput(
            title="Python",
            course_weeks=weeks,
        )

        result = validate_generation_output(
            output,
            mode="full_course",
            course_weeks=2,
            classes_per_week=2,
        )

        self.assertIs(result, output)

    def test_full_course_rejects_nonconsecutive_session_numbers(self):
        output = LessonOutput(
            title="Python",
            course_weeks=[
                CourseWeek(
                    week_number=1,
                    title="Week 1",
                    sessions=[
                        CourseSession(
                            session_number=2,
                            title="Introduction",
                            topic="Python basics",
                            learning_objectives=[
                                "Explain the purpose of Python."
                            ],
                            content=(
                                "Python is a programming language "
                                "used to build applications and "
                                "automate repetitive tasks."
                            ),
                        )
                    ],
                )
            ],
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="full_course",
                course_weeks=1,
                classes_per_week=1,
            )
