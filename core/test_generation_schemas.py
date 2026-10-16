
from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from core.generation_schemas import (
    LessonActivity,
    LessonOutput,
    LessonQuestion,
    LessonSection,
    LearningObjective,
)


class GenerationSchemaTests(SimpleTestCase):
    def test_lesson_output_has_expected_defaults(self):
        output = LessonOutput(title="Introduction to Python")

        self.assertEqual(output.title, "Introduction to Python")
        self.assertEqual(output.introduction, "")
        self.assertEqual(output.learning_objectives, [])
        self.assertEqual(output.sections, [])
        self.assertEqual(output.questions, [])
        self.assertEqual(output.activities, [])
        self.assertEqual(output.sources, [])

    def test_lesson_sections_store_heading_and_content(self):
        section = LessonSection(
            heading="Variables",
            content="Variables store values.",
        )

        self.assertEqual(section.heading, "Variables")
        self.assertEqual(section.content, "Variables store values.")

    def test_learning_objective_stores_description(self):
        objective = LearningObjective(
            description="Explain how variables work."
        )

        self.assertEqual(
            objective.description,
            "Explain how variables work.",
        )

    def test_question_defaults_to_short_answer(self):
        question = LessonQuestion(
            question="What is a variable?",
            answer="A named reference to a value.",
        )

        self.assertEqual(question.question_type, "short_answer")

    def test_activity_defaults_to_class_activity(self):
        activity = LessonActivity(
            title="Practice",
            instructions="Create three variables.",
        )

        self.assertEqual(activity.activity_type, "class_activity")

    def test_default_lists_are_independent(self):
        first = LessonOutput(title="Lesson One")
        second = LessonOutput(title="Lesson Two")

        first.key_points.append("A key point")

        self.assertEqual(second.key_points, [])

    def test_output_is_immutable(self):
        output = LessonOutput(title="Introduction")

        with self.assertRaises(FrozenInstanceError):
            output.title = "Changed title"
