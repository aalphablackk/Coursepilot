import json

from django.test import SimpleTestCase

from .generation_parser import GenerationOutputError, parse_generation_output
from .generation_validation import validate_generation_output


class GenerationModeValidationTests(SimpleTestCase):
    def setUp(self):
        self.base_output = {
            "title": "Test Lesson",
            "introduction": "An introduction.",
            "learning_objectives": [{"description": "Understand the topic"}],
            "sections": [{"heading": "Basics", "content": "Core explanation."}],
            "key_points": [],
            "examples": [],
            "fun_facts": [],
            "questions": [],
            "activities": [],
            "assignment": "Complete a practice task.",
            "conclusion": "Review the main idea.",
            "teaching_notes": "",
            "presentation_slides": [],
            "course_weeks": [],
            "sources": [],
            "metadata": {},
        }

    def parse_output(self, data):
        return parse_generation_output(json.dumps(data))

    def test_summary_requires_sections(self):
        data = {**self.base_output, "sections": []}
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="summary")

    def test_presentation_requires_slides(self):
        output = self.parse_output(self.base_output)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="presentation")

    def test_presentation_rejects_untitled_slide(self):
        data = {
            **self.base_output,
            "presentation_slides": [
                {"title": " ", "bullet_points": ["Key idea"], "speaker_notes": ""}
            ],
        }
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="presentation")

    def test_custom_content_accepts_introduction_without_sections(self):
        data = {
            **self.base_output,
            "introduction": "Reorganized source content.",
            "sections": [],
        }
        output = self.parse_output(data)

        validated = validate_generation_output(
            output,
            mode="custom_content",
        )
        self.assertEqual(validated.introduction, "Reorganized source content.")

    def test_custom_content_rejects_empty_content(self):
        data = {
            **self.base_output,
            "introduction": " ",
            "sections": [],
        }
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="custom_content")

    def test_full_course_rejects_missing_schedule_arguments(self):
        output = self.parse_output(self.base_output)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="full_course")

    def test_full_course_rejects_non_positive_schedule(self):
        output = self.parse_output(self.base_output)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="full_course",
                course_weeks=0,
                classes_per_week=2,
            )

    def test_full_course_rejects_wrong_number_of_weeks(self):
        output = self.parse_output(self.base_output)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(
                output,
                mode="full_course",
                course_weeks=2,
                classes_per_week=1,
            )
