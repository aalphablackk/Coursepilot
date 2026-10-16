from types import SimpleNamespace

from django.test import SimpleTestCase

from core.generation_utils import (
    is_incomplete_response,
    split_text_into_chunks,
)


class GenerationUtilsTests(SimpleTestCase):

    def test_detects_output_token_limit(self):
        response = SimpleNamespace(
            finish_reason="MAX_TOKENS",
            metadata={},
        )

        self.assertTrue(is_incomplete_response(response))

    def test_detects_incomplete_status(self):
        response = SimpleNamespace(
            finish_reason=None,
            metadata={"response_status": "incomplete"},
        )

        self.assertTrue(is_incomplete_response(response))

    def test_accepts_completed_response(self):
        response = SimpleNamespace(
            finish_reason="STOP",
            metadata={"response_status": "completed"},
        )

        self.assertFalse(is_incomplete_response(response))

    def test_splits_long_text(self):
        text = ("A" * 100) + "\n\n" + ("B" * 100)

        chunks = split_text_into_chunks(text, max_chars=120)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunks))
        self.assertEqual(
            "".join(chunks).replace(" ", "").replace("\n", ""),
            text.replace(" ", "").replace("\n", ""),
        )
    def test_preserves_text_when_reassembled(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        chunks = split_text_into_chunks(text, max_chars=25)

        self.assertEqual(
            "".join(chunks).replace(" ", "").replace("\n", ""),
            text.replace(" ", "").replace("\n", ""),
        )
    def test_rejects_invalid_chunk_size(self):
        with self.assertRaises(ValueError):
            split_text_into_chunks("Example", max_chars=0)