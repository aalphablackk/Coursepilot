
from django.test import SimpleTestCase

from core.prompt_builder import build_generation_prompt


from django.test import SimpleTestCase

from core.prompt_builder import (
    MODE_OUTPUT_REQUIREMENTS,
    OUTPUT_CONTRACT,
    build_generation_prompt,
)


class GenerationPromptBuilderTests(SimpleTestCase):
    def test_every_mode_has_specific_output_requirements(self):
        expected_phrases = {
            "quick_lesson": "measurable learning objectives",
            "summary": "Preserve the source",
            "presentation": "presentation_slides",
            "custom_content": "selected action",
            "full_course": "exactly the requested number",
        }

        for mode, phrase in expected_phrases.items():
            with self.subTest(mode=mode):
                self.assertIn(phrase, MODE_OUTPUT_REQUIREMENTS[mode])

    def test_question_contract_contains_all_supported_fields(self):
        for field in (
            '"question"',
            '"answer"',
            '"question_type"',
            '"options"',
            '"explanation"',
            '"hint"',
            '"section_heading"',
        ):
            with self.subTest(field=field):
                self.assertIn(field, OUTPUT_CONTRACT)

    def test_quick_lesson_prompt_includes_mode_and_quality_requirements(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python functions",
            "learner_level": "beginner",
            "detail_level": "standard",
            "duration_minutes": 45,
        })

        self.assertIn("Python functions", prompt)
        self.assertIn("45 minutes", prompt)
        self.assertIn("MODE-SPECIFIC OUTPUT REQUIREMENTS", prompt)
        self.assertIn("measurable learning objectives", prompt)

    def test_custom_content_prompt_includes_selected_action(self):
        prompt = build_generation_prompt({
            "mode": "custom_content",
            "topic": "Database normalization",
            "source_text": "Normalization reduces data redundancy.",
            "content_action": "simplify",
            "learner_level": "intermediate",
            "detail_level": "standard",
        })

        self.assertIn("CONTENT ACTION:", prompt)
        self.assertIn("more accessible language", prompt)
        self.assertIn("Normalization reduces data redundancy.", prompt)

    def test_full_course_prompt_preserves_requested_schedule(self):
        prompt = build_generation_prompt({
            "mode": "full_course",
            "topic": "Web development",
            "learner_level": "beginner",
            "detail_level": "standard",
            "course_weeks": 8,
            "classes_per_week": 4,
            "class_duration_minutes": 90,
        })

        self.assertIn("Duration: 8 weeks.", prompt)
        self.assertIn("Classes per week: 4.", prompt)
        self.assertIn("Total scheduled classes: 32.", prompt)
        self.assertIn("every scheduled session", prompt.lower())

class PromptBuilderTests(SimpleTestCase):
    def test_quick_lesson_includes_topic_and_duration(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Computer Networks",
            "learner_level": "beginner",
            "detail_level": "standard",
            "duration_minutes": 60,
        })

        self.assertIn("Computer Networks", prompt)
        self.assertIn("60 minutes", prompt)
        self.assertIn("learning objectives", prompt.lower())

    def test_full_course_includes_exact_schedule(self):
        prompt = build_generation_prompt({
            "mode": "full_course",
            "topic": "Python Programming",
            "learner_level": "intermediate",
            "detail_level": "detailed",
            "course_weeks": 8,
            "classes_per_week": 4,
            "class_duration_minutes": 90,
        })

        self.assertIn("8 weeks", prompt)
        self.assertIn("Classes per week: 4", prompt)
        self.assertIn("32", prompt)
        self.assertIn("90", prompt)

    def test_custom_content_includes_content_action(self):
        prompt = build_generation_prompt({
            "mode": "custom_content",
            "source_text": "My lecture notes",
            "content_action": "simplify",
            "learner_level": "beginner",
            "detail_level": "concise",
        })

        self.assertIn("My lecture notes", prompt)
        self.assertIn("CONTENT ACTION", prompt)
        self.assertIn("accessible language", prompt)

    def test_research_instructions_do_not_claim_research_was_done(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Artificial Intelligence",
            "use_web_research": True,
        })

        self.assertIn("when provided", prompt)
        self.assertIn("Never invent citations", prompt)

    def test_research_sources_are_included_when_provided(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Django security",
            "use_web_research": True,
            "research_sources": [
                {
                    "title": "Official Django Security Guide",
                    "url": "https://docs.djangoproject.com/en/stable/topics/security/",
                    "content": "Django provides built-in protections against common web attacks.",
                }
            ],
        })

        self.assertIn("RETRIEVED RESEARCH SOURCES:", prompt)
        self.assertIn("Official Django Security Guide", prompt)
        self.assertIn(
            "https://docs.djangoproject.com/en/stable/topics/security/",
            prompt,
        )
        self.assertIn(
            "Django provides built-in protections against common web attacks.",
            prompt,
        )

    def test_missing_research_results_do_not_claim_current_verification(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Artificial Intelligence",
            "use_web_research": True,
        })

        self.assertIn("No research results were supplied", prompt)
        self.assertIn(
            "Do not claim that the lesson has been verified against current web sources.",
            prompt,
        )

    def test_research_instructions_are_absent_when_research_is_disabled(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Python",
            "use_web_research": False,
        })

        self.assertNotIn("WEB RESEARCH:", prompt)
        self.assertNotIn("RETRIEVED RESEARCH SOURCES:", prompt)

    def test_invalid_research_sources_are_skipped(self):
        prompt = build_generation_prompt({
            "mode": "quick_lesson",
            "topic": "Django",
            "use_web_research": True,
            "research_sources": [
                "not a dictionary",
                {
                    "title": "Missing URL",
                    "content": "This source has no URL.",
                },
                {
                    "title": "Missing content",
                    "url": "https://example.com/incomplete",
                },
                {
                    "title": "Valid source",
                    "url": "https://example.com/valid",
                    "content": "This is valid research content.",
                },
            ],
        })

        self.assertIn("Valid source", prompt)
        self.assertIn("https://example.com/valid", prompt)
        self.assertIn("This is valid research content.", prompt)
        self.assertNotIn("Missing URL", prompt)
        self.assertNotIn("Missing content", prompt)
        self.assertNotIn("This source has no URL.", prompt)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            build_generation_prompt({"mode": "unknown"})

    def test_invalid_learner_level_is_rejected(self):
        with self.assertRaises(ValueError):
            build_generation_prompt({
                "mode": "quick_lesson",
                "learner_level": "unknown",
            })

    def test_invalid_detail_level_is_rejected(self):
        with self.assertRaises(ValueError):
            build_generation_prompt({
                "mode": "quick_lesson",
                "detail_level": "unknown",
            })

    def test_each_mode_has_its_own_output_requirements(self):
        cases = {
            "quick_lesson": "measurable learning objectives",
            "summary": "Preserve the source",
            "presentation": "presentation_slides",
            "custom_content": "selected action",
            "full_course": "exactly the requested number",
        }

        for mode, expected_text in cases.items():
            with self.subTest(mode=mode):
                prompt = build_generation_prompt({
                    "mode": mode,
                    "topic": "Test topic",
                    "source_text": "Test source material",
                    "duration_minutes": 60,
                    "course_weeks": 8,
                    "classes_per_week": 4,
                    "class_duration_minutes": 90,
                })
                self.assertIn(expected_text, prompt)

    def test_presentation_requires_slide_structure(self):
        prompt = build_generation_prompt({
            "mode": "presentation",
            "topic": "Computer Networks",
        })

        self.assertIn("presentation_slides", prompt)
        self.assertIn("bullet_points", prompt)
        self.assertIn("speaker_notes", prompt)

    def test_full_course_requires_complete_schedule(self):
        prompt = build_generation_prompt({
            "mode": "full_course",
            "topic": "Python",
            "course_weeks": 8,
            "classes_per_week": 4,
            "class_duration_minutes": 90,
        })

        self.assertIn("Total scheduled classes: 32", prompt)
        self.assertIn("Do not omit sessions", prompt)


