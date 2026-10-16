
import json

from django.test import SimpleTestCase

from core.course_chunk_parser import parse_course_session_batch
from core.generation_parser import GenerationOutputError
from core.generation_schemas import CourseSession


class CourseChunkParserTests(SimpleTestCase):

    def test_parses_valid_session_batch(self):
        quiz_questions = [
            {
                "question": f"What is the purpose of concept {i}?",
                "answer": f"Option A: Purpose {i}",
                "question_type": "multiple_choice",
                "options": [
                    f"Option A: Purpose {i}",
                    f"Option B: Alternative {i}",
                    f"Option C: Another alternative {i}",
                    f"Option D: Final alternative {i}",
                ],
                "explanation": f"Option A is correct because it explains concept {i}.",
                "hint": f"Review concept {i}.",
                "section_heading": f"Section {i}",
            }
            for i in range(1, 11)
        ]
        payload = {
            "sessions": [
                {
                    "session_number": 1,
                    "title": "Python Fundamentals",
                    "topic": "Variables and data types",
                    "learning_objectives": [
                        "Explain variables",
                        "Identify common data types",
                    ],
                    "content": (
                        "This session introduces the topic in detail. Learners will explore "
                        "the main concepts, follow guided examples, practise the techniques, "
                        "discuss common mistakes, and complete independent exercises. "
                        * 35
                    ),
                    "activity": "Create variables for a simple profile.",
                    "quiz_questions": quiz_questions,
                    "assignment": "Write a short program.",
                    "teaching_notes": "Demonstrate each example.",
                }
            ]
        }

        result = parse_course_session_batch(json.dumps(payload))

        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], CourseSession)
        self.assertEqual(result[0].session_number, 1)
        self.assertEqual(result[0].title, "Python Fundamentals")

    def test_rejects_invalid_json(self):
        with self.assertRaises(GenerationOutputError):
            parse_course_session_batch('{"sessions": [')

    def test_rejects_empty_batch(self):
        with self.assertRaises(GenerationOutputError):
            parse_course_session_batch('{"sessions": []}')

    def test_rejects_session_without_objectives(self):
        payload = {
            "sessions": [
                {
                    "session_number": 1,
                    "title": "Python Fundamentals",
                    "topic": "Variables",
                    "learning_objectives": [],
                }
            ]
        }

        with self.assertRaises(GenerationOutputError):
            parse_course_session_batch(json.dumps(payload))

    def test_rejects_session_without_title(self):
        payload = {
            "sessions": [
                {
                    "session_number": 1,
                    "title": "",
                    "topic": "Variables",
                    "learning_objectives": ["Explain variables"],
                }
            ]
        }

        with self.assertRaises(GenerationOutputError):
            parse_course_session_batch(json.dumps(payload))
