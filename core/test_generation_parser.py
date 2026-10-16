
import json

from django.test import SimpleTestCase

from core.generation_parser import (
    GenerationOutputError,
    parse_generation_output,
)


class GenerationParserTests(SimpleTestCase):
    def valid_payload(self):
        return {
            "title": "Introduction to Python",
            "introduction": "A beginner-friendly introduction.",
            "learning_objectives": [
                {"description": "Explain what Python is."}
            ],
            "sections": [
                {"heading": "Overview", "content": "Python is a language."}
            ],
            "key_points": ["Python is widely used."],
            "examples": ["print('Hello')"],
            "fun_facts": [],
            "questions": [
                {
                    "question": "What is Python?",
                    "answer": "A programming language.",
                    "question_type": "short_answer",
                }
            ],
            "activities": [],
            "assignment": "Write a small program.",
            "conclusion": "Review the main concepts.",
            "teaching_notes": "Demonstrate the code live.",
            "presentation_slides": [
                {
                    "title": "Overview",
                    "bullet_points": ["Python is readable."],
                    "speaker_notes": "Introduce the language.",
                }
            ],
            "course_weeks": [
                {
                    "week_number": 1,
                    "title": "Foundations",
                    "learning_goals": ["Understand the basics."],
                    "sessions": [
                        {
                            "session_number": 1,
                            "title": "First steps",
                            "topic": "Python basics",
                            "learning_objectives": ["Run a Python program."],
                            "content": "Install and run Python.",
                            "activity": "Write a print statement.",
                            "quiz_questions": [],
                            "assignment": "Write a short script.",
                            "teaching_notes": "Check each learner's output.",
                        }
                    ],
                }
            ],
            "sources": [],
            "metadata": {},
        }

    def test_valid_output_is_parsed(self):
        result = parse_generation_output(json.dumps(self.valid_payload()))

        self.assertEqual(result.title, "Introduction to Python")
        self.assertEqual(
            result.learning_objectives[0].description,
            "Explain what Python is.",
        )
        self.assertEqual(result.presentation_slides[0].title, "Overview")
        self.assertEqual(result.course_weeks[0].sessions[0].session_number, 1)

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(GenerationOutputError):
            parse_generation_output("{invalid json")

    def test_empty_response_is_rejected(self):
        with self.assertRaises(GenerationOutputError):
            parse_generation_output("")

    def test_missing_required_field_is_rejected(self):
        payload = self.valid_payload()
        del payload["title"]

        with self.assertRaises(GenerationOutputError):
            parse_generation_output(json.dumps(payload))

    def test_wrong_field_type_is_rejected(self):
        payload = self.valid_payload()
        payload["key_points"] = "This should be a list."

        with self.assertRaises(GenerationOutputError):
            parse_generation_output(json.dumps(payload))
