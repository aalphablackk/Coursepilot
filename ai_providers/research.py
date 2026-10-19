
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

    @staticmethod
    def _build_search_queries(query: str) -> list[dict[str, Any]]:
        """Build complementary searches and apply freshness when relevant."""
        topic = query.strip()

        prefix = "Current, reliable educational information about:"
        suffix = ". Prioritize official documentation and authoritative sources."

        if topic.startswith(prefix):
            topic = topic[len(prefix):].strip()

        if topic.endswith(suffix):
            topic = topic[:-len(suffix)].strip()

        topic = topic.rstrip(".").strip()

        if not topic:
            return []

        freshness_keywords = (
            "latest",
            "recent",
            "current",
            "new",
            "updated",
            "updates",
            "2026",
            "release notes",
            "what's new",
            "what is new",
        )

        topic_lower = topic.lower()
        needs_freshness = any(
            keyword in topic_lower
            for keyword in freshness_keywords
        )

        return [
            {
                "query": topic,
                "time_range": None,
            },
            {
                "query": f"{topic} official documentation reference guide",
                "time_range": None,
            },
            {
                "query": f"{topic} latest updates release notes",
                "time_range": "month" if needs_freshness else None,
            },
        ]

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search multiple query variations and return unique sources."""
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

        sources_by_url: dict[str, dict[str, Any]] = {}

        for search_params in self._build_search_queries(query):
            try:
                response = self.client.search(
                    query=search_params["query"],
                    max_results=max_results,
                    search_depth="advanced",
                    include_raw_content="markdown",
                    **(
                        {"time_range": search_params["time_range"]}
                        if search_params["time_range"]
                        else {}
                    ),
                )
            except Exception as exc:
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

            for item in results:
                if not isinstance(item, dict):
                    continue

                url = item.get("url")
                content = item.get("raw_content") or item.get("content")

                if not self._is_valid_http_url(url):
                    continue

                if not isinstance(content, str) or not content.strip():
                    continue

                url = url.strip()
                deduplication_key = url.split("#", 1)[0].rstrip("/")

                title = item.get("title")
                score = item.get("score")

                source = {
                    "title": (
                        title.strip()
                        if isinstance(title, str) and title.strip()
                        else "Untitled source"
                    ),
                    "url": url,
                    "content": content.strip(),
                    "score": (
                        score
                        if isinstance(score, (int, float))
                        and not isinstance(score, bool)
                        else None
                    ),
                }

                existing = sources_by_url.get(deduplication_key)

                if existing is None or (
                    source["score"] is not None
                    and (
                        existing["score"] is None
                        or source["score"] > existing["score"]
                    )
                ):
                    sources_by_url[deduplication_key] = source

        ranked_sources = sorted(
            sources_by_url.values(),
            key=lambda source: (
                source["score"] is not None,
                source["score"] if source["score"] is not None else 0,
            ),
            reverse=True,
        )

        return ranked_sources[:max_results]
