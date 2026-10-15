
from typing import Any

from django.conf import settings
from tavily import TavilyClient

from .exceptions import (
    AIProviderNotConfiguredError,
    AIProviderUnavailableError,
    AIProviderResponseError,
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

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Return normalized web search results with source URLs."""
        if not query or not query.strip():
            raise AIProviderResponseError(
                "A search query is required."
            )

        if not 1 <= max_results <= 10:
            raise AIProviderResponseError(
                "max_results must be between 1 and 10."
            )

        try:
            response = self.client.search(
                query=query.strip(),
                max_results=max_results,
                search_depth="basic",
            )
        except Exception as exc:
            raise AIProviderUnavailableError(
                "Web research failed. Please try again."
            ) from exc

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

            if not isinstance(url, str) or not url.startswith(
                ("https://", "http://")
            ):
                continue

            if not isinstance(content, str) or not content.strip():
                continue

            normalized_results.append({
                "title": str(item.get("title") or "Untitled source"),
                "url": url,
                "content": content.strip(),
                "score": item.get("score"),
            })

        return normalized_results
