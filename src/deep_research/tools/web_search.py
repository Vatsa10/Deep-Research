"""Tavily web search tool for the research pipeline."""

from __future__ import annotations

import os

import httpx


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using Tavily API.

    Args:
        query: The search query string (2-6 keywords recommended).
        max_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: title, url, content, score.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return [{"error": "TAVILY_API_KEY not set"}]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_raw_content": False,
                "search_depth": "advanced",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in data.get("results", [])
    ]
