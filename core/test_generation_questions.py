import json

from django.test import SimpleTestCase

from .generation_parser import (
    GenerationOutputError,
    parse_generation_output,
)


class GenerationQuestionParserTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "title": "Computer Networks",
            "introduction": "An introduction.",
            "learning_objectives": [],
            "sections": [],
            "key_points": [],
            "examples": [],
            "fun_facts": [],
            "questions": [],
            "activities": [],
            "assignment": "",
            "conclusion": "",
            "teaching_notes": "",
            "presentation_slides": [],
            "course_weeks": [],
            "sources": [],
            "metadata": {},
        }

    def parse(self, questions):
        data = {**self.data, "questions": questions}
        return parse_generation_output(json.dumps(data))

    def test_parses_multiple_choice_question(self):
        output = self.parse([{
            "question": "What connects devices?",
            "question_type": "multiple_choice",
            "options": ["A network", "A keyboard", "A monitor"],
            "answer": "A network",
            "explanation": "Networks enable device communication.",
            "hint": "Think about connected devices.",
            "section_heading": "Network Basics",
        }])

        question = output.questions[0]
        self.assertEqual(len(question.options), 3)
        self.assertEqual(question.answer, "A network")
        self.assertEqual(
            question.explanation,
            "Networks enable device communication.",
        )
        self.assertEqual(question.hint, "Think about connected devices.")
        self.assertEqual(question.section_heading, "Network Basics")

    def test_old_question_format_remains_supported(self):
        output = self.parse([{
            "question": "What is a network?",
            "answer": "Connected devices",
        }])

        question = output.questions[0]
        self.assertEqual(question.question_type, "short_answer")
        self.assertEqual(question.options, [])
        self.assertEqual(question.explanation, "")
        self.assertEqual(question.hint, "")

    def test_rejects_options_that_are_not_a_list(self):
        with self.assertRaises(GenerationOutputError):
            self.parse([{
                "question": "What connects devices?",
                "options": "A network",
            }])

    def test_rejects_non_string_option(self):
        with self.assertRaises(GenerationOutputError):
            self.parse([{
                "question": "What connects devices?",
                "options": ["A network", 42],
            }])
