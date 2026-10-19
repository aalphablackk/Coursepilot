
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ai_providers.exceptions import (
    AIProviderNotConfiguredError,
    AIProviderResponseError,
    AIProviderUnavailableError,
)
from ai_providers.factory import get_ai_provider
from ai_providers.exceptions import AIProviderError
from ai_providers.gemini import GeminiProvider
from ai_providers.openai import OpenAIProvider
from ai_providers.research import WebResearchService
import openai

from ai_providers.exceptions import (
    AIProviderAuthenticationError,
    AIProviderQuotaExceededError,
    AIProviderRateLimitError,
    AIProviderTemporaryError,
    AIProviderAuthenticationError,
    AIProviderQuotaExceededError,
)

@override_settings(
    GEMINI_API_KEY="test-key",
    GEMINI_MODEL="primary-model",
    GEMINI_FALLBACK_MODEL="fallback-model",
)
class GeminiProviderTests(SimpleTestCase):
    @patch("ai_providers.gemini.genai.Client")
    def test_primary_model_success(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.return_value = SimpleNamespace(
            text="Generated lesson",
            usage_metadata=SimpleNamespace(
                prompt_token_count=120,
                candidates_token_count=80,
                total_token_count=200,
            ),
            candidates=[
                SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))
            ],
        )

        provider = GeminiProvider()
        result = provider.generate_text("Explain Python")

        self.assertEqual(result.content, "Generated lesson")
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "primary-model")
        mock_client.models.generate_content.assert_called_once()
        self.assertEqual(
            mock_client.models.generate_content.call_args.kwargs["model"],
            "primary-model",
        )
        self.assertEqual(result.usage.input_tokens, 120)
        self.assertEqual(result.usage.output_tokens, 80)
        self.assertEqual(result.usage.total_tokens, 200)
        self.assertEqual(result.finish_reason, "STOP")

    @patch("ai_providers.gemini.genai.Client")
    def test_authentication_error_does_not_trigger_fallback(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        error = AIProviderAuthenticationError("Invalid credentials")
        mock_client.models.generate_content.side_effect = error

        provider = GeminiProvider()

        with self.assertRaises(AIProviderAuthenticationError):
            provider.generate_text("Explain Python")

        mock_client.models.generate_content.assert_called_once()

    @patch("ai_providers.gemini.genai.Client")
    def test_quota_error_does_not_trigger_fallback(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        error = AIProviderQuotaExceededError("Quota exhausted")
        mock_client.models.generate_content.side_effect = error

        provider = GeminiProvider()

        with self.assertRaises(AIProviderQuotaExceededError):
            provider.generate_text("Explain Python")

        mock_client.models.generate_content.assert_called_once()

    @patch("ai_providers.gemini.genai.Client")
    def test_fallback_model_used_when_primary_fails(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = [
            RuntimeError("Primary unavailable"),
            SimpleNamespace(text="Fallback lesson"),
        ]

        provider = GeminiProvider()
        result = provider.generate_text("Explain Python")

        self.assertEqual(result.content, "Fallback lesson")
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "fallback-model")
        self.assertEqual(
            [
                call.kwargs["model"]
                for call in mock_client.models.generate_content.call_args_list
            ],
            ["primary-model", "fallback-model"],
        )

    @patch("ai_providers.gemini.genai.Client")
    def test_error_when_both_models_fail(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError(
            "Provider unavailable"
        )

        provider = GeminiProvider()

        with self.assertRaises(AIProviderUnavailableError):
            provider.generate_text("Explain Python")

        self.assertEqual(
            mock_client.models.generate_content.call_count,
            2,
        )

    @override_settings(GEMINI_FALLBACK_MODEL="")
    @patch("ai_providers.gemini.genai.Client")
    def test_no_fallback_when_not_configured(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError(
            "Primary unavailable"
        )

        provider = GeminiProvider()

        with self.assertRaises(AIProviderUnavailableError):
            provider.generate_text("Explain Python")

        mock_client.models.generate_content.assert_called_once()

    @override_settings(GEMINI_API_KEY="")
    def test_missing_api_key_raises_configuration_error(self):
        with self.assertRaises(AIProviderNotConfiguredError):
            GeminiProvider()

@override_settings(
    OPENAI_API_KEY="test-key",
    OPENAI_MODEL="test-model",
)
class OpenAIProviderTests(SimpleTestCase):
    @patch("ai_providers.openai.OpenAI")
    def test_successful_generation(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.return_value = SimpleNamespace(
            output_text="Generated lesson",
            model="test-model",
            status="completed",
            _request_id="req_test123",
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=80,
                total_tokens=200,
            ),
        )

        provider = OpenAIProvider()
        result = provider.generate_text(
            "Explain Python",
            system_instruction="You are a helpful instructor.",
        )

        self.assertEqual(result.content, "Generated lesson")
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.model, "test-model")
        mock_client.responses.create.assert_called_once()

        call_kwargs = mock_client.responses.create.call_args.kwargs
        self.assertIsNotNone(result.usage)
        self.assertEqual(call_kwargs["model"], "test-model")
        self.assertEqual(
            call_kwargs["max_output_tokens"],
            8192,
        )
        self.assertEqual(
            call_kwargs["input"][0]["role"],
            "system",
        )
        self.assertEqual(result.usage.input_tokens, 120)
        self.assertEqual(result.usage.output_tokens, 80)
        self.assertEqual(result.usage.total_tokens, 200)
        self.assertEqual(result.finish_reason, "completed")
        self.assertEqual(result.request_id, "req_test123")

    @patch("ai_providers.openai.OpenAI")
    def test_api_error_is_wrapped(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.side_effect = RuntimeError(
            "Simulated API failure"
        )

        provider = OpenAIProvider()

        with self.assertRaises(AIProviderUnavailableError):
            provider.generate_text("Explain Python")

    @patch("ai_providers.openai.OpenAI")
    def test_empty_prompt_is_rejected(self, mock_openai_class):
        provider = OpenAIProvider()

        with self.assertRaises(AIProviderResponseError):
            provider.generate_text("   ")

        mock_openai_class.assert_called_once()

    @patch("ai_providers.openai.OpenAI")
    def test_empty_response_is_rejected(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.return_value = SimpleNamespace(
            output_text="   "
        )

        provider = OpenAIProvider()

        with self.assertRaises(AIProviderResponseError):
            provider.generate_text("Explain Python")

    @patch("ai_providers.openai.OpenAI")
    def test_authentication_error_is_classified(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.side_effect = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401, headers={}),
            body={"error": {"message": "Invalid API key"}},
        )

        provider = OpenAIProvider()

        with self.assertRaises(AIProviderAuthenticationError):
            provider.generate_text("Explain Python")

    @patch("ai_providers.openai.OpenAI")
    def test_rate_limit_error_is_classified(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.side_effect = openai.RateLimitError(
            message="Too many requests",
            response=MagicMock(status_code=429, headers={}),
            body={"error": {"message": "Too many requests", "code": "rate_limit_exceeded"}},
        )

        provider = OpenAIProvider()

        with self.assertRaises(AIProviderRateLimitError):
            provider.generate_text("Explain Python")

    @patch("ai_providers.openai.OpenAI")
    def test_quota_error_is_classified(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.responses.create.side_effect = openai.RateLimitError(
            message="Quota exceeded",
            response=MagicMock(status_code=429, headers={}),
            body={
                "error": {
                    "message": "Quota exceeded",
                    "code": "insufficient_quota",
                }
            },
        )

        provider = OpenAIProvider()

        with self.assertRaises(AIProviderQuotaExceededError):
            provider.generate_text("Explain Python")

    @override_settings(OPENAI_API_KEY="")
    def test_missing_api_key_is_rejected(self):
        with self.assertRaises(AIProviderNotConfiguredError):
            OpenAIProvider()


@override_settings(AI_PROVIDER="gemini")
class AIProviderFactoryTests(SimpleTestCase):
    @patch.dict(
        "ai_providers.factory.PROVIDER_CLASSES",
        {"gemini": MagicMock(name="GeminiProvider")},
    )
    def test_selects_default_gemini_provider(self):
        from ai_providers.factory import PROVIDER_CLASSES

        provider_class = PROVIDER_CLASSES["gemini"]
        provider = get_ai_provider()

        provider_class.assert_called_once_with()
        self.assertEqual(provider, provider_class.return_value)

    def test_empty_provider_name_is_rejected(self):
        with self.assertRaises(AIProviderError):
            get_ai_provider("")

    def test_whitespace_provider_name_is_rejected(self):
        with self.assertRaises(AIProviderError):
            get_ai_provider("   ")

    @override_settings(AI_PROVIDER=None)
    def test_non_string_default_is_rejected(self):
        with self.assertRaises(AIProviderError):
            get_ai_provider()

    @patch.dict(
        "ai_providers.factory.PROVIDER_CLASSES",
        {"openai": MagicMock(name="OpenAIProvider")},
    )
    def test_selects_explicit_openai_provider(self):
        from ai_providers.factory import PROVIDER_CLASSES

        provider_class = PROVIDER_CLASSES["openai"]
        provider = get_ai_provider("openai")

        provider_class.assert_called_once_with()
        self.assertEqual(provider, provider_class.return_value)

    def test_unsupported_provider_is_rejected(self):
        with self.assertRaises(AIProviderError):
            get_ai_provider("unsupported")

    @override_settings(AI_PROVIDER="invalid")
    def test_invalid_default_provider_is_rejected(self):
        with self.assertRaises(AIProviderError):
            get_ai_provider()




@override_settings(TAVILY_API_KEY="test-tavily-key")
class WebResearchServiceTests(SimpleTestCase):

    @patch("ai_providers.research.TavilyClient")
    def test_malformed_response_is_rejected(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {"results": "invalid"}

        service = WebResearchService()

        with self.assertRaises(AIProviderResponseError):
            service.search("Python")

    @patch("ai_providers.research.TavilyClient")
    def test_malformed_http_urls_are_excluded(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Malformed URL",
                    "url": "https://",
                    "content": "Should be excluded.",
                },
                {
                    "title": "Whitespace URL",
                    "url": "https://exa mple.com",
                    "content": "Should also be excluded.",
                },
                {
                    "title": "Valid source",
                    "url": "https://example.com/python",
                    "content": "Useful source content.",
                },
            ]
        }

        service = WebResearchService()
        results = service.search("Python")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Valid source")

    @patch("ai_providers.research.TavilyClient")
    def test_successful_search_returns_normalized_sources(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Python Documentation",
                    "url": "https://docs.python.org/3/",
                    "content": "Python is a programming language.",
                    "score": 0.95,
                }
            ]
        }

        service = WebResearchService()
        results = service.search("Introduction to Python")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python Documentation")
        self.assertEqual(
            results[0]["url"],
            "https://docs.python.org/3/",
        )
        self.assertEqual(
            results[0]["content"],
            "Python is a programming language.",
        )
        self.assertEqual(mock_client.search.call_count, 3)

        first_call = mock_client.search.call_args_list[0]
        self.assertEqual(
            first_call.kwargs["query"],
            "Introduction to Python",
        )
        self.assertEqual(first_call.kwargs["max_results"], 5)
        self.assertEqual(first_call.kwargs["search_depth"], "advanced")
        self.assertEqual(
            first_call.kwargs["include_raw_content"],
            "markdown",
        )

    @patch("ai_providers.research.TavilyClient")
    def test_raw_content_is_preferred_when_available(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Official Documentation",
                    "url": "https://example.com/docs",
                    "content": "Short search excerpt.",
                    "raw_content": "Full extracted documentation content.",
                }
            ]
        }

        service = WebResearchService()
        results = service.search("Python documentation")

        self.assertEqual(
            results[0]["content"],
            "Full extracted documentation content.",
        )
    @override_settings(TAVILY_API_KEY="")
    def test_missing_api_key_is_rejected(self):
        with self.assertRaises(AIProviderNotConfiguredError):
            WebResearchService()

    @patch("ai_providers.research.TavilyClient")
    def test_empty_query_is_rejected(self, mock_client_class):
        service = WebResearchService()

        with self.assertRaises(AIProviderResponseError):
            service.search("   ")

        mock_client_class.return_value.search.assert_not_called()

    @patch("ai_providers.research.TavilyClient")
    def test_invalid_result_limit_is_rejected(self, mock_client_class):
        service = WebResearchService()

        with self.assertRaises(AIProviderResponseError):
            service.search("Python", max_results=20)

        mock_client_class.return_value.search.assert_not_called()

    @patch("ai_providers.research.TavilyClient")
    def test_search_failure_is_wrapped(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.side_effect = RuntimeError(
            "Simulated Tavily failure"
        )

        service = WebResearchService()

        with self.assertRaises(AIProviderUnavailableError):
            service.search("Python")

    @patch("ai_providers.research.TavilyClient")
    def test_invalid_sources_are_excluded(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Invalid URL",
                    "url": "javascript:alert(1)",
                    "content": "Should be excluded.",
                },
                {
                    "title": "Missing content",
                    "url": "https://example.com/",
                    "content": "   ",
                },
                {
                    "title": "Valid source",
                    "url": "https://example.com/python",
                    "content": "Useful source content.",
                },
            ]
        }

        service = WebResearchService()
        results = service.search("Python")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Valid source")

    @patch("ai_providers.research.TavilyClient")
    def test_search_queries_include_documentation_and_updates(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {"results": []}
        service = WebResearchService()
        service.search(
            "Current, reliable educational information about: Django 6. "
            "Prioritize official documentation and authoritative sources."
        )
        queries = [
            call.kwargs["query"]
            for call in mock_client.search.call_args_list
        ]
        calls = mock_client.search.call_args_list
        self.assertNotIn("time_range", calls[0].kwargs)
        self.assertNotIn("time_range", calls[1].kwargs)
        self.assertNotIn("time_range", calls[2].kwargs)
        self.assertEqual(len(queries), 3)
        self.assertEqual(queries[0], "Django 6")
        self.assertIn("official documentation", queries[1])
        self.assertIn("release notes", queries[2])

    @patch("ai_providers.research.TavilyClient")
    def test_freshness_filter_is_used_for_recent_topics(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {"results": []}

        service = WebResearchService()
        service.search("latest Django updates")

        calls = mock_client.search.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[2].kwargs["time_range"], "month")

    @patch("ai_providers.research.TavilyClient")
    def test_duplicate_urls_are_removed_across_searches(
        self, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Python Documentation",
                    "url": "https://example.com/docs",
                    "content": "Documentation content.",
                    "score": 0.9,
                },
                {
                    "title": "Duplicate URL",
                    "url": "https://example.com/docs#section",
                    "content": "Duplicate content.",
                    "score": 0.8,
                },
            ]
        }
        service = WebResearchService()
        results = service.search("Python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python Documentation")