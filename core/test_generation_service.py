
from unittest.mock import Mock, patch
from django.test import TestCase, SimpleTestCase
from ai_providers.exceptions import AIProviderUnavailableError
from ai_providers.schemas import AIResponse

from .generation_parser import GenerationOutputError
from .services import LessonGenerationError, generate_lesson

import json


from .generation_parser import GenerationOutputError, parse_generation_output
from .generation_validation import validate_generation_output


class GenerationValidationTests(SimpleTestCase):
    def setUp(self):
        self.valid_output = {
            "title": "Introduction to Computer Networks",
            "introduction": "A computer network connects devices.",
            "learning_objectives": [
                {"description": "Define a computer network"}
            ],
            "sections": [
                {
                    "heading": "Network Basics",
                    "content": "Devices communicate over networks.",
                }
            ],
            "key_points": ["Networks connect devices"],
            "examples": ["A home Wi-Fi network"],
            "fun_facts": [],
            "questions": [],
            "activities": [],
            "assignment": "List three network devices.",
            "conclusion": "Networks allow devices to communicate.",
            "teaching_notes": "",
            "presentation_slides": [],
            "course_weeks": [],
            "sources": [],
            "metadata": {},
        }

    def parse_output(self, data=None):
        return parse_generation_output(
            json.dumps(data if data is not None else self.valid_output)
        )

    def test_accepts_valid_quick_lesson(self):
        output = self.parse_output()

        validated = validate_generation_output(
            output,
            mode="quick_lesson",
        )

        self.assertEqual(validated.title, self.valid_output["title"])

    def test_rejects_quick_lesson_without_objectives(self):
        data = {**self.valid_output, "learning_objectives": []}
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="quick_lesson")

    def test_rejects_quick_lesson_without_sections(self):
        data = {**self.valid_output, "sections": []}
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="quick_lesson")

    def test_rejects_empty_title(self):
        data = {**self.valid_output, "title": "   "}
        output = self.parse_output(data)

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="quick_lesson")

    def test_rejects_unsupported_mode(self):
        output = self.parse_output()

        with self.assertRaises(GenerationOutputError):
            validate_generation_output(output, mode="unknown_mode")

class LessonGenerationServiceTests(TestCase):
    def setUp(self):
        self.data = {
            "mode": "quick_lesson",
            "topic": "Introduction to computer networks",
            "source_text": "",
            "learner_level": "beginner",
            "detail_level": "standard",
            "content_action": "organize",
            "duration_minutes": 30,
        }


        self.valid_json = """
        {
            "title": "Introduction to Computer Networks",
            "introduction": "A computer network connects devices.",
            "learning_objectives": [
                {"description": "Define a computer network"}
            ],
            "sections": [
                {
                    "heading": "Network Basics",
                    "content": "Devices communicate over networks."
                }
            ],
            "key_points": [],
            "examples": [],
            "fun_facts": [],
            "questions": [],
            "activities": [],
            "assignment": "List three network devices.",
            "conclusion": "Networks allow devices to communicate.",
            "teaching_notes": "",
            "presentation_slides": [],
            "course_weeks": [],
            "sources": [],
            "metadata": {
                "duration_plan": {
                    "total_minutes": 30,
                    "stages": [
                        {
                            "name": "Introduction",
                            "minutes": 5
                        },
                        {
                            "name": "Teaching",
                            "minutes": 15
                        },
                        {
                            "name": "Practice",
                            "minutes": 7
                        },
                        {
                            "name": "Conclusion",
                            "minutes": 3
                        }
                    ]
                }
            }
        }
        """


    @patch("core.services.get_ai_provider")
    def test_generates_and_validates_lesson(self, mock_get_provider):
        provider = Mock()
        provider.generate_text.return_value = AIResponse(
            content=self.valid_json,
            provider="gemini",
            model="test-model",
        )
        mock_get_provider.return_value = provider

        output, response = generate_lesson(self.data)

        self.assertEqual(output.title, "Introduction to Computer Networks")
        self.assertEqual(response.provider, "gemini")
        provider.generate_text.assert_called_once()

    @patch("core.services.get_ai_provider")
    def test_provider_failure_becomes_generation_error(self, mock_get_provider):
        mock_get_provider.return_value.generate_text.side_effect = (
            AIProviderUnavailableError("Provider unavailable")
        )

        with self.assertRaises(LessonGenerationError):
            generate_lesson(self.data)

    @patch("core.services.get_ai_provider")
    def test_invalid_json_becomes_generation_error(self, mock_get_provider):
        mock_get_provider.return_value.generate_text.return_value = AIResponse(
            content="not valid JSON",
            provider="gemini",
            model="test-model",
        )

        with self.assertRaises(LessonGenerationError):
            generate_lesson(self.data)
from unittest.mock import patch

from django.test import SimpleTestCase

from core.services import generate_lesson, LessonGenerationError


class GenerationServiceErrorTests(TestCase):

    @patch("core.services.get_ai_provider")
    def test_unexpected_provider_error_becomes_safe_generation_error(
        self, mock_get_provider
    ):
        mock_get_provider.side_effect = RuntimeError(
            "Internal provider details"
        )

        with self.assertRaises(LessonGenerationError) as context:
            generate_lesson({
                "mode": "quick_lesson",
                "topic": "Python variables",
                "learner_level": "beginner",
                "detail_level": "standard",
                "content_action": "organize",
                "duration_minutes": 30,
            })

        self.assertEqual(
            str(context.exception),
            "We couldn't complete your lesson right now. Please try again later.",
        )
        self.assertNotIn(
            "Internal provider details",
            str(context.exception),
        )
