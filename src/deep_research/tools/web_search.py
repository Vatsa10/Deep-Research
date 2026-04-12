"""Web search tool — DuckDuckGo (free, no API key) with Tavily fallback."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


def _ddg_search(query: str, max_results: int) -> list[dict]:
    """Run DuckDuckGo search synchronously (the library is sync-only)."""
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
                "score": 0.0,
            })
    return results


async def web_search(query: str, max_results: int = 5) -> ToolResponse:
    """Search the web for information.

    Uses DuckDuckGo (free, no API key required) by default.
    Falls back to Tavily if TAVILY_API_KEY is set and DDG fails.

    Args:
        query: The search query string (2-6 keywords recommended).
        max_results: Maximum number of results to return.

    Returns:
        ToolResponse with JSON string of results (title, url, content).
    """
    import asyncio

    # Try DuckDuckGo first (free)
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _executor, _ddg_search, query, max_results
        )
        if results:
            return ToolResponse(content=json.dumps(results, ensure_ascii=False))
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)

    # Fallback to Tavily if API key is available
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if tavily_key:
        try:
            return await _tavily_search(query, max_results, tavily_key)
        except Exception as exc:
            logger.warning("Tavily fallback failed: %s", exc)

    return ToolResponse(content=json.dumps(
        [{"title": "Search failed", "url": "", "content": f"No results found for: {query}", "score": 0}]
    ))


async def _tavily_search(query: str, max_results: int, api_key: str) -> ToolResponse:
    """Tavily search as a fallback."""
    import httpx

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

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in data.get("results", [])
    ]

    return ToolResponse(content=json.dumps(results, ensure_ascii=False))
