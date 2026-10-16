
from django.test import SimpleTestCase

from core.generation_schemas import (
    CourseSession,
    CourseWeek,
    LessonOutput,
    LessonQuestion,
    LessonSection,
)
from core.generation_output_normalizer import normalize_output


class GenerationOutputNormalizerTests(SimpleTestCase):

    def test_normalizes_nested_course_content(self):
        output = LessonOutput(
            title="Python — Foundations",
            sections=[
                LessonSection(
                    heading="Variables — Basics",
                    content="Variables — store values.",
                )
            ],
            course_weeks=[
                CourseWeek(
                    week_number=1,
                    title="Week — One",
                    sessions=[
                        CourseSession(
                            session_number=1,
                            title="Session — One",
                            topic="Python — Basics",
                            learning_objectives=["Explain variables — clearly"],
                            quiz_questions=[
                                LessonQuestion(
                                    question="What is a variable — in Python?",
                                    answer="A named reference — to a value.",
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        normalized = normalize_output(output)

        self.assertIsInstance(normalized, LessonOutput)
        self.assertNotIn("—", normalized.title)
        self.assertNotIn("—", normalized.sections[0].content)

        session = normalized.course_weeks[0].sessions[0]
        self.assertNotIn("—", session.topic)
        self.assertNotIn("—", session.quiz_questions[0].question)

    def test_preserves_non_text_values(self):
        output = CourseWeek(
            week_number=2,
            title="Week — Two",
        )

        normalized = normalize_output(output)

        self.assertEqual(normalized.week_number, 2)
        self.assertEqual(normalized.title, "Week, Two")
