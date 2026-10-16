
from types import SimpleNamespace

from django.test import SimpleTestCase

from core.generation_response_checks import is_response_truncated


class GenerationResponseChecksTests(SimpleTestCase):
    def make_response(self, finish_reason=None, metadata=None):
        return SimpleNamespace(
            finish_reason=finish_reason,
            metadata=metadata or {},
        )

    def test_detects_openai_output_token_limit(self):
        response = self.make_response(
            finish_reason="max_output_tokens",
            metadata={
                "response_status": "incomplete",
                "incomplete_reason": "max_output_tokens",
            },
        )
        self.assertTrue(is_response_truncated(response))

    def test_detects_gemini_max_tokens(self):
        response = self.make_response(finish_reason="MAX_TOKENS")
        self.assertTrue(is_response_truncated(response))

    def test_detects_length_finish_reason(self):
        response = self.make_response(finish_reason="length")
        self.assertTrue(is_response_truncated(response))

    def test_does_not_flag_completed_response(self):
        response = self.make_response(
            finish_reason="completed",
            metadata={"response_status": "completed"},
        )
        self.assertFalse(is_response_truncated(response))

    def test_does_not_flag_unrelated_incomplete_reason(self):
        response = self.make_response(
            finish_reason="incomplete",
            metadata={
                "response_status": "incomplete",
                "incomplete_reason": "content_filter",
            },
        )
        self.assertFalse(is_response_truncated(response))

    def test_handles_missing_metadata(self):
        response = self.make_response(finish_reason=None)
        self.assertFalse(is_response_truncated(response))
