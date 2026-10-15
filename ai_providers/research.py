
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from tavily import TavilyClient

from .exceptions import (
    AIProviderNotConfiguredError,
    AIProviderResponseError,
    AIProviderTemporaryError,
    AIProviderUnavailableError,
)


class WebResearchService:
    """Search the web for source material to support lesson generation."""

    def __init__(self) -> None:
        api_key = getattr(settings, "TAVILY_API_KEY", "")

        if not api_key:
            raise AIProviderNotConfiguredError(
                "Web research is not configured on this server."
            )

        self.client = TavilyClient(api_key=api_key)

    @staticmethod
    def _is_valid_http_url(url: Any) -> bool:
        """Accept only absolute HTTP(S) URLs with a hostname."""
        if not isinstance(url, str) or not url.strip():
            return False

        try:
            parsed = urlparse(url.strip())
            return (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.hostname)
                and not any(char.isspace() for char in url)
            )
        except (ValueError, TypeError):
            return False

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Return normalized search results with source URLs."""
        if not isinstance(query, str) or not query.strip():
            raise AIProviderResponseError("A search query is required.")

        if (
            not isinstance(max_results, int)
            or isinstance(max_results, bool)
            or not 1 <= max_results <= 10
        ):
            raise AIProviderResponseError(
                "max_results must be an integer between 1 and 10."
            )

        try:
            response = self.client.search(
                query=query.strip(),
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as exc:
            # Do not expose provider details or credentials to users.
            raise AIProviderUnavailableError(
                "Web research failed. Please try again."
            ) from exc

        if not isinstance(response, dict):
            raise AIProviderResponseError(
                "The research service returned an invalid response."
            )

        results = response.get("results", [])

        if not isinstance(results, list):
            raise AIProviderResponseError(
                "The research service returned an invalid response."
            )

        normalized_results = []

        for item in results:
            if not isinstance(item, dict):
                continue

            url = item.get("url")
            content = item.get("content")

            if not self._is_valid_http_url(url):
                continue

            if not isinstance(content, str) or not content.strip():
                continue

            title = item.get("title")
            score = item.get("score")

            normalized_results.append({
                "title": title.strip() if isinstance(title, str) and title.strip() else "Untitled source",
                "url": url.strip(),
                "content": content.strip(),
                "score": score if isinstance(score, (int, float)) and not isinstance(score, bool) else None,
            })

        return normalized_results
