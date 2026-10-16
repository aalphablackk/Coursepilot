
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from core.course_outline_generator import (
    CourseOutlineGenerationError,
    _parse_and_validate_outline_batch,
    generate_course_outline_batch,
)
from core.generation_parser import GenerationOutputError


class CourseOutlineValidationTests(SimpleTestCase):
    def make_payload(self):
        return {
            "weeks": [
                {
                    "week_number": 1,
                    "title": "Foundations",
                    "learning_goals": ["Understand the fundamentals"],
                    "sessions": [
                        {
                            "session_number": 1,
                            "title": "Introduction",
                            "topic": "Core concepts",
                            "learning_objectives": ["Explain the key concepts"],
                        },
                        {
                            "session_number": 2,
                            "title": "First principles",
                            "topic": "Basic principles",
                            "learning_objectives": ["Identify core principles"],
                        },
                    ],
                }
            ]
        }

    def validate(self, payload):
        return _parse_and_validate_outline_batch(
            json.dumps(payload),
            expected_weeks=[1],
            classes_per_week=2,
            first_session=1,
            last_session=2,
        )

    def test_accepts_valid_outline(self):
        result = self.validate(self.make_payload())
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["sessions"]), 2)

    def test_rejects_missing_week(self):
        with self.assertRaises(GenerationOutputError):
            self.validate({"weeks": []})

    def test_rejects_wrong_session_numbers(self):
        payload = self.make_payload()
        payload["weeks"][0]["sessions"][1]["session_number"] = 4

        with self.assertRaises(GenerationOutputError):
            self.validate(payload)

    def test_rejects_missing_objectives(self):
        payload = self.make_payload()
        payload["weeks"][0]["sessions"][0]["learning_objectives"] = []

        with self.assertRaises(GenerationOutputError):
            self.validate(payload)

    def test_normalizes_em_dash(self):
        payload = self.make_payload()
        payload["weeks"][0]["sessions"][0]["title"] = "Python — basics"

        result = self.validate(payload)
        self.assertEqual(result[0]["sessions"][0]["title"], "Python - basics")

    def test_rejects_invalid_json(self):
        with self.assertRaises(GenerationOutputError):
            _parse_and_validate_outline_batch(
                "{not json",
                expected_weeks=[1],
                classes_per_week=2,
                first_session=1,
                last_session=2,
            )


class CourseOutlineGeneratorTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "topic": "Python programming",
            "learner_level": "beginner",
            "detail_level": "standard",
            "course_weeks": 2,
            "classes_per_week": 2,
            "class_duration_minutes": 60,
            "source_text": "",
        }

    def test_rejects_start_week_beyond_schedule(self):
        with self.assertRaises(ValueError):
            generate_course_outline_batch(self.data, start_week=3)

    def test_rejects_nonpositive_batch_size(self):
        with self.assertRaises(ValueError):
            generate_course_outline_batch(self.data, week_count=0)

    @patch("core.course_outline_generator.get_ai_provider")
    @patch("core.course_outline_generator.AIConfiguration.get_active_provider")
    def test_retries_invalid_output(
        self, mock_active_provider, mock_factory
    ):
        mock_active_provider.return_value = "openai"
        provider = mock_factory.return_value
        provider.generate_text.return_value.content = "{invalid"

        with self.assertRaises(CourseOutlineGenerationError):
            generate_course_outline_batch(
                self.data,
                start_week=1,
                week_count=1,
            )

        self.assertEqual(provider.generate_text.call_count, 3)
