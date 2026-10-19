
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Course, Lesson
from unittest.mock import patch
from core.prompt_builder import build_generation_prompt
User = get_user_model()

from django.test import TestCase

from .forms import GenerationForm, MAX_SOURCE_LENGTH


class GenerationValidationRegressionTests(TestCase):
    """Regression tests for generation form validation."""

    def valid_data(self, **overrides):
        data = {
            "mode": "quick_lesson",
            "topic": "Introduction to Python",
            "learner_level": "intermediate",
            "detail_level": "standard",
            "content_action": "organize",
            "duration_minutes": "60",
            "course_weeks": "4",
            "classes_per_week": "2",
            "class_duration_minutes": "60",
            "source_text": "",
        }
        data.update(overrides)
        return data

    def test_empty_submission_is_rejected(self):
        form = GenerationForm({})
        self.assertFalse(form.is_valid())

    def test_whitespace_topic_without_source_is_rejected(self):
        form = GenerationForm(
            self.valid_data(topic="   ", source_text="   ")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("topic", form.errors)

    def test_quick_lesson_requires_duration(self):
        form = GenerationForm(
            self.valid_data(duration_minutes="")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("duration_minutes", form.errors)

    def test_full_course_requires_complete_schedule(self):
        form = GenerationForm(
            self.valid_data(
                mode="full_course",
                course_weeks="",
                classes_per_week="",
                class_duration_minutes="",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("course_weeks", form.errors)
        self.assertIn("classes_per_week", form.errors)
        self.assertIn("class_duration_minutes", form.errors)

    def test_full_course_accepts_complete_schedule(self):
        form = GenerationForm(
            self.valid_data(mode="full_course")
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_web_research_is_optional_and_defaults_to_false(self):
        form = GenerationForm(self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["use_web_research"])

    def test_web_research_can_be_enabled(self):
        form = GenerationForm(
            self.valid_data(use_web_research="on")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data["use_web_research"])

    def test_source_text_at_limit_is_accepted(self):
        form = GenerationForm(
            self.valid_data(
                mode="custom_content",
                topic="",
                source_text="x" * MAX_SOURCE_LENGTH,
            )
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_source_text_over_limit_is_rejected(self):
        form = GenerationForm(
            self.valid_data(
                mode="custom_content",
                topic="",
                source_text="x" * (MAX_SOURCE_LENGTH + 1),
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("source_text", form.errors)
@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class GenerationViewTests(TestCase):
    # Keep all four existing test methods here.
    """Test the actual generation page response."""
    form_data = {
        "mode": "quick_lesson",
        "topic": "Becoming a Man",
        "learner_level": "intermediate",
        "detail_level": "standard",
        "duration_minutes": 60,
        "content_action": "organize",
    }

    def valid_post_data(self):
        return {
            "mode": "quick_lesson",
            "topic": "Introduction to Python",
            "learner_level": "intermediate",
            "detail_level": "standard",
            "duration_minutes": "60",
            "source_text": "",
        }

    def test_generation_page_loads(self):
        response = self.client.get(reverse("core:generate"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create learning content")

    def test_empty_post_does_not_show_success_message(self):
        response = self.client.post(reverse("core:generate"), {})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Your inputs are valid.")


    @patch("core.views.generate_lesson_task.delay")
    def test_valid_post_queues_lesson_generation(self, mock_task):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("core:generate"),
                self.form_data,
            )

        self.assertEqual(response.status_code, 200)

        lesson = Lesson.objects.get(topic="Becoming a Man")

        self.assertEqual(
            lesson.generation_status,
            Lesson.GenerationStatus.GENERATING,
        )
        self.assertContains(response, "generation-progress")
        mock_task.assert_called_once()

    # @patch("core.views.generate_lesson")
    # def test_valid_post_generates_lesson(self, mock_generate_lesson):
    #     from core.generation_schemas import LessonOutput
    #     from ai_providers.schemas import AIResponse

    #     mock_generate_lesson.return_value = (
    #         LessonOutput(
    #             title="Becoming a Man",
    #             introduction="An introduction to personal growth.",
    #         ),
    #         AIResponse(
    #             content='{"title": "Becoming a Man"}',
    #             provider="gemini",
    #             model="test-model",
    #         ),
    #     )

    #     response = self.client.post(
    #         reverse("core:generate"),
    #         self.form_data,
    #         follow=True,
    #     )

    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, "Becoming a Man")

    #     self.assertEqual(len(response.redirect_chain), 1)
    #     self.assertEqual(
    #         response.redirect_chain[0][0],
    #         f"/lessons/{Lesson.objects.latest('created_at').id}/",
    #     )

    #     mock_generate_lesson.assert_called_once()

    def test_missing_duration_displays_error_not_success(self):
        data = self.valid_post_data()
        data["duration_minutes"] = ""

        response = self.client.post(reverse("core:generate"), data)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Your inputs are valid.")
        self.assertContains(response, "Enter the class duration.")

class GenerationFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "mode": "quick_lesson",
            "topic": "Introduction to Python",
            "learner_level": "intermediate",
            "duration_minutes": "60",
            "detail_level": "standard",
            "content_action": "organize",
            "source_text": "",
            "course_weeks": "4",
            "classes_per_week": "2",
            "class_duration_minutes": "60",
        }
        data.update(overrides)
        return data

    def test_custom_content_requires_text(self):
        form = GenerationForm(self.valid_data(
            mode="custom_content",
            topic="",
            source_text="   ",
        ))

        self.assertFalse(form.is_valid())
        self.assertIn("source_text", form.errors)

    def test_custom_content_accepts_pasted_text(self):
        form = GenerationForm(self.valid_data(
            mode="custom_content",
            topic="",
            source_text="These are my lecture notes.",
        ))

        self.assertTrue(form.is_valid(), form.errors)

    def test_source_text_at_maximum_length_is_accepted(self):
        form = GenerationForm(self.valid_data(
            mode="custom_content",
            topic="",
            source_text="x" * MAX_SOURCE_LENGTH,
        ))

        self.assertTrue(form.is_valid(), form.errors)

    def test_source_text_over_maximum_length_is_rejected(self):
        form = GenerationForm(self.valid_data(
            mode="custom_content",
            topic="",
            source_text="x" * (MAX_SOURCE_LENGTH + 1),
        ))

        self.assertFalse(form.is_valid())
        self.assertIn("source_text", form.errors)

    def test_invalid_generation_mode_is_rejected(self):
        form = GenerationForm(self.valid_data(mode="unknown_mode"))

        self.assertFalse(form.is_valid())
        self.assertIn("mode", form.errors)

    def test_invalid_duration_is_rejected(self):
        form = GenerationForm(self.valid_data(duration_minutes="2"))

        self.assertFalse(form.is_valid())
        self.assertIn("duration_minutes", form.errors)

    def test_topic_is_required_for_quick_lesson_without_source(self):
        form = GenerationForm(
            self.valid_data(
                mode="quick_lesson",
                topic="",
                source_text="",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("topic", form.errors)


class CourseModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="coursepilot_test",
            password="test-password-123",
        )

    def test_course_defaults_to_private_draft(self):
        course = Course.objects.create(
            creator=self.user,
            title="Introduction to Python",
        )

        self.assertEqual(course.status, Course.Status.DRAFT)
        self.assertTrue(course.slug)
        self.assertEqual(course.learner_level, "intermediate")

    def test_course_slug_is_unique(self):
        first = Course.objects.create(
            creator=self.user,
            title="Introduction to Python",
        )
        second = Course.objects.create(
            creator=self.user,
            title="Introduction to Python",
        )

        self.assertNotEqual(first.slug, second.slug)

    def test_course_string_representation(self):
        course = Course.objects.create(
            creator=self.user,
            title="Data Science",
        )

        self.assertEqual(str(course), "Data Science")


class LessonModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lessonpilot_test",
            password="test-password-123",
        )

    def test_standalone_lesson_can_be_created(self):
        lesson = Lesson.objects.create(
            creator=self.user,
            title="Python Variables",
            topic="Variables in Python",
        )

        self.assertIsNone(lesson.course)
        self.assertEqual(lesson.generation_mode, Lesson.GenerationMode.QUICK_LESSON)

    def test_lesson_can_belong_to_a_course(self):
        course = Course.objects.create(
            creator=self.user,
            title="Python Fundamentals",
        )
        lesson = Lesson.objects.create(
            creator=self.user,
            course=course,
            title="Python Variables",
        )

        self.assertEqual(lesson.course, course)
        self.assertIn(lesson, course.lessons.all())

    def test_lesson_supports_presentation_content(self):
        lesson = Lesson.objects.create(
            creator=self.user,
            title="Climate Change Presentation",
            generation_mode=Lesson.GenerationMode.PRESENTATION,
            presentation_content={
                "slides": [
                    {
                        "title": "Introduction",
                        "bullets": ["Definition", "Causes"],
                        "speaker_notes": "Introduce the topic.",
                    }
                ]
            },
        )

        self.assertEqual(
            lesson.presentation_content["slides"][0]["title"],
            "Introduction",
        )


class ResearchPromptBuilderTests(TestCase):
    def setUp(self):
        self.data = {
            "mode": "quick_lesson",
            "learner_level": "intermediate",
            "detail_level": "detailed",
            "topic": "Bootstrap updates",
            "duration_minutes": 60,
            "use_web_research": True,
        }

    def test_research_sources_are_included_in_prompt(self):
        self.data["research_sources"] = [
            {
                "title": "Official Bootstrap Documentation",
                "url": "https://getbootstrap.com/docs/",
                "content": "Bootstrap documentation and component updates.",
            }
        ]

        prompt = build_generation_prompt(self.data)

        self.assertIn("RETRIEVED RESEARCH SOURCES", prompt)
        self.assertIn("Official Bootstrap Documentation", prompt)
        self.assertIn("https://getbootstrap.com/docs/", prompt)
        self.assertIn(
            "Bootstrap documentation and component updates.",
            prompt,
        )

    def test_missing_research_sources_are_not_claimed_as_verified(self):
        prompt = build_generation_prompt(self.data)

        self.assertIn("No research results were supplied", prompt)
        self.assertNotIn("RETRIEVED RESEARCH SOURCES", prompt)

    def test_research_disabled_does_not_include_research_content(self):
        self.data["use_web_research"] = False
        self.data["research_sources"] = [
            {
                "title": "Private test source",
                "url": "https://example.com/",
                "content": "Private test content.",
            }
        ]

        prompt = build_generation_prompt(self.data)

        self.assertNotIn("Private test source", prompt)
        self.assertNotIn("Private test content.", prompt)

    def test_learner_levels_have_distinct_instructional_guidance(self):
        beginner = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "learner_level": "beginner",
        })
        intermediate = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "learner_level": "intermediate",
        })
        advanced = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "learner_level": "advanced",
        })

        self.assertIn("new to the subject", beginner)
        self.assertIn("small logical steps", beginner)
        self.assertIn("fundamentals", intermediate)
        self.assertIn("how and why concepts work", intermediate)
        self.assertIn("assumptions", advanced)
        self.assertIn("edge cases", advanced)

    def test_detail_levels_have_distinct_depth_guidance(self):
        prompts = {
            level: build_generation_prompt({
                "mode": "quick_lesson",
                "topic": "Python functions",
                "learner_level": "intermediate",
                "detail_level": level,
            })
            for level in ("concise", "standard", "detailed")
        }

        self.assertIn("focused treatment", prompts["concise"])
        self.assertIn("balanced, instructor-ready treatment", prompts["standard"])
        self.assertIn("comprehensive, well-developed treatment", prompts["detailed"])
        self.assertIn("worked examples", prompts["detailed"])
        self.assertNotEqual(prompts["concise"], prompts["detailed"])

    def test_duration_requires_realistic_time_allocation(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "duration_minutes": 30,
        })

        self.assertIn("SESSION DURATION: 30 minutes.", prompt)
        self.assertIn("add up to the requested session duration", prompt)
        self.assertIn("specific minute values", prompt)
        self.assertIn("learner practice", prompt)

    def test_duration_guidance_adapts_to_requested_duration(self):
        short_prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "duration_minutes": 30,
        })
        long_prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "duration_minutes": 90,
        })

        self.assertIn("SESSION DURATION: 30 minutes.", short_prompt)
        self.assertIn("SESSION DURATION: 90 minutes.", long_prompt)
        self.assertIn(
            "Prioritize essential learning objectives",
            short_prompt,
        )
        self.assertIn(
            "Prioritize essential learning objectives",
            long_prompt,
        )

    def test_duration_guidance_is_omitted_when_not_provided(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
        })

        self.assertNotIn("SESSION DURATION:", prompt)
