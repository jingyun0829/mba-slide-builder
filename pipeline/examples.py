"""Fetch recent, real-world examples for an MBA topic via Tavily.

Returns [] gracefully if no API key or the package isn't installed —
the outline generator will still work on Claude's own knowledge.
"""
from __future__ import annotations

import os
from typing import Any


def fetch_recent_examples(topic: str, max_results: int = 6, days: int = 540) -> list[dict[str, Any]]:
    """days: time window for case freshness.
       540 ≈ 18 months (default), 180 ≈ 6 months (latest cases mode).
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or not topic.strip():
        return []

    try:
        from tavily import TavilyClient
    except ImportError:
        return []

    client = TavilyClient(api_key=api_key)
    query = f"recent business case or real-world example: {topic}"

    try:
        results = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            topic="news",
            days=days,
        )
    except Exception:
        return []

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
            "date": r.get("published_date", ""),
        }
        for r in results.get("results", [])
    ]
