
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.course_chunk_generator import (
    CourseChunkGenerationError,
    generate_course_session_batch,
)


class CourseChunkGeneratorTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "mode": "full_course",
            "topic": "Python programming",
            "learner_level": "beginner",
            "detail_level": "standard",
            "course_weeks": 2,
            "classes_per_week": 2,
            "duration_minutes": 60,
            "source_text": "",
        }

    
    def make_response(self, numbers):
        sessions = []

        for number in numbers:
            questions = [
                {
                    "question": f"What is the purpose of concept {index}?",
                    "answer": f"Option A: Purpose {index}",
                    "question_type": "multiple_choice",
                    "options": [
                        f"Option A: Purpose {index}",
                        f"Option B: Alternative {index}",
                        f"Option C: Another alternative {index}",
                        f"Option D: Final alternative {index}",
                    ],
                    "explanation": f"Option A is correct because it explains concept {index}.",
                    "hint": f"Review concept {index}.",
                    "section_heading": f"Section {index}",
                }
                for index in range(1, 11)
            ]

            sessions.append({
                "session_number": number,
                "title": f"Session {number}",
                "topic": f"Topic {number}",
                "learning_objectives": ["Explain the topic"],
                "content": (
                    "This session introduces the topic in detail. "
                    "Learners will explore the main concepts, follow guided "
                    "examples, practise the techniques, discuss common mistakes, "
                    "and complete independent exercises. " * 35
                ),
                "activity": "Practice the concept.",
                "quiz_questions": questions,
                "assignment": "Complete a short exercise.",
                "teaching_notes": "Demonstrate the example.",
            })

        return SimpleNamespace(
            content=json.dumps({"sessions": sessions}),
            provider="openai",
            model="test-model",
            finish_reason="completed",
            usage=None,
            metadata={},
        )


    @patch("core.course_chunk_generator.get_ai_provider")
    @patch("core.course_chunk_generator.AIConfiguration.get_active_provider")
    def test_generates_requested_batch(self, mock_active_provider, mock_factory):
        mock_active_provider.return_value = "openai"
        provider = mock_factory.return_value
        provider.generate_text.return_value = self.make_response([1, 2])

        sessions, response = generate_course_session_batch(
            self.data,
            start_session=1,
            session_count=2,
        )

        self.assertEqual([s.session_number for s in sessions], [1, 2])
        self.assertEqual(response.provider, "openai")
        provider.generate_text.assert_called_once()

    @patch("core.course_chunk_generator.get_ai_provider")
    @patch("core.course_chunk_generator.AIConfiguration.get_active_provider")
    def test_rejects_wrong_session_numbers(
        self, mock_active_provider, mock_factory
    ):
        mock_active_provider.return_value = "openai"
        mock_factory.return_value.generate_text.return_value = (
            self.make_response([2, 3])
        )

        with self.assertRaises(CourseChunkGenerationError):
            generate_course_session_batch(
                self.data,
                start_session=1,
                session_count=2,
            )

    def test_rejects_start_session_beyond_schedule(self):
        with self.assertRaises(ValueError):
            generate_course_session_batch(
                self.data,
                start_session=5,
                session_count=2,
            )

    def test_rejects_invalid_batch_size(self):
        with self.assertRaises(ValueError):
            generate_course_session_batch(
                self.data,
                start_session=1,
                session_count=0,
            )
