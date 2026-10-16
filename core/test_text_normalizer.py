
from django.test import SimpleTestCase

from core.text_normalizer import normalize_generated_text


class TextNormalizerTests(SimpleTestCase):

    def test_removes_em_dash(self):
        result = normalize_generated_text(
            "Python is useful — it automates repetitive tasks."
        )
        self.assertNotIn("—", result)

    def test_preserves_text_meaning(self):
        result = normalize_generated_text(
            "The model — which was trained earlier — produced an answer."
        )
        self.assertIn("model", result)
        self.assertIn("produced an answer", result)

    def test_handles_multiple_em_dashes(self):
        result = normalize_generated_text("Learn — practise — improve.")
        self.assertNotIn("—", result)

    def test_handles_empty_text(self):
        self.assertEqual(normalize_generated_text(""), "")

    def test_preserves_text_without_em_dash(self):
        text = "Learn Python, practise daily, and build projects."
        self.assertEqual(normalize_generated_text(text), text)
