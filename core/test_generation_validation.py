
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

    def _make_duration_plan(self, stages=None, total_minutes=30):
        output = LessonOutput(
            title="Python Basics",
            learning_objectives=[

                    "Explain the purpose of Python."

            ],
            sections=[
                LessonSection(
                    heading="Introduction",
                    content=(
                        "Python is a programming language used "
                        "to build applications and automate tasks."
                    ),
                )
            ],
            metadata={
                "duration_plan": {
                    "total_minutes": total_minutes,
                    "stages": stages
                    if stages is not None
                    else [
                        {"name": "Introduction", "minutes": 5},
                        {"name": "Teaching", "minutes": 15},
                        {"name": "Practice", "minutes": 7},
                        {"name": "Conclusion", "minutes": 3},
                    ],
                }
            },
        )
        return output

    def test_quick_lesson_accepts_valid_duration_plan(self):
        output = self._make_duration_plan()

        result = validate_generation_output(
            output,
            mode="quick_lesson",
            duration_minutes=30,
        )

        self.assertIs(result, output)

    def test_presentation_accepts_valid_duration_plan(self):
        output = LessonOutput(
            title="Networking",
            learning_objectives=[

                    "Explain the purpose of computer networks."

            ],
            presentation_slides=[
                PresentationSlide(
                    title="Introduction",
                    bullet_points=[
                        "Networks connect devices.",
                        "Protocols define communication rules.",
                    ],
                    speaker_notes=(
                        "Explain how connected devices communicate."
                    ),
                )
            ],
            metadata={
                "duration_plan": {
                    "total_minutes": 30,
                    "stages": [
                        {"name": "Introduction", "minutes": 5},
                        {"name": "Teaching", "minutes": 15},
                        {"name": "Discussion", "minutes": 7},
                        {"name": "Conclusion", "minutes": 3},
                    ],
                }
            },
        )

        result = validate_generation_output(
            output,
            mode="presentation",
            duration_minutes=30,
        )

        self.assertIs(result, output)


    def test_duration_plan_is_required_when_duration_is_provided(self):
        output = LessonOutput(
            title="Python Basics",
            learning_objectives=[
                "Explain the purpose of Python."
            ],
            sections=[
                LessonSection(
                    heading="Introduction",
                    content=(
                        "Python is a programming language used "
                        "to build applications and automate tasks."
                    ),
                )
            ],
            metadata={},
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
                duration_minutes=30,
            )


    def test_duration_plan_total_must_match_requested_duration(self):
        output = self._make_duration_plan(total_minutes=25)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
                duration_minutes=30,
            )

    def test_duration_stages_must_add_up_to_requested_duration(self):
        output = self._make_duration_plan(
            stages=[
                {"name": "Introduction", "minutes": 5},
                {"name": "Teaching", "minutes": 10},
            ]
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
                duration_minutes=30,
            )

    def test_duration_plan_rejects_empty_stages(self):
        output = self._make_duration_plan(stages=[])

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
                duration_minutes=30,
            )

    def test_duration_plan_rejects_invalid_stage_minutes(self):
        invalid_values = [0, -1, 1.5, True, "5"]

        for minutes in invalid_values:
            with self.subTest(minutes=minutes):
                output = self._make_duration_plan(
                    stages=[
                        {"name": "Introduction", "minutes": minutes},
                    ]
                )

                with self.assertRaises(GenerationOutputError):
                    validate_generation_output(
                        output,
                        mode="quick_lesson",
                        duration_minutes=30,
                    )

    def test_duration_plan_rejects_missing_stage_name(self):
        output = self._make_duration_plan(
            stages=[
                {"name": " ", "minutes": 30},
            ]
        )

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="quick_lesson",
                duration_minutes=30,
            )

    def test_summary_does_not_require_duration_plan(self):
        output = LessonOutput(
            title="Python",
            sections=[
                LessonSection(
                    heading="Overview",
                    content=(
                        "Python is a programming language used "
                        "for general-purpose programming."
                    ),
                )
            ],
        )

        result = validate_generation_output(
            output,
            mode="summary",
            duration_minutes=30,
        )

        self.assertIs(result, output)
