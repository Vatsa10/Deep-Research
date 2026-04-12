"""Web search tools — multiple search strategies the agent can choose from."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4)


def _ddg_text(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS
    results = []
    with DDGS() as d:
        for r in d.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
            })
    return results


def _ddg_news(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS
    results = []
    with DDGS() as d:
        for r in d.news(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("body", ""),
                "date": r.get("date", ""),
                "source": r.get("source", ""),
            })
    return results


def _ddg_quick(query: str) -> list[dict]:
    """Use a focused text search to get a quick factual answer."""
    from ddgs import DDGS
    results = []
    with DDGS() as d:
        for r in d.text(f"{query} answer", max_results=2):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
            })
    return results


async def web_search(query: str, max_results: int = 5) -> ToolResponse:
    """Search the web for information relevant to the query.

    Uses DuckDuckGo (free, no API key). Searches regular web results.
    Use site-specific queries for targeted results, e.g.:
    - "site:github.com langchain agents" for GitHub repos
    - "site:linkedin.com/in/ John Doe AI" for LinkedIn profiles
    - "site:arxiv.org transformer attention" for papers

    Args:
        query: Search query (2-8 keywords). Supports site: operator.
        max_results: Number of results to return (default 5).

    Returns:
        JSON list of {title, url, content} for each result.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(_executor, _ddg_text, query, max_results)
        if results:
            return ToolResponse(content=json.dumps(results, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)

    # Tavily fallback
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if tavily_key:
        try:
            return await _tavily_search(query, max_results, tavily_key)
        except Exception as exc:
            logger.warning("Tavily fallback failed: %s", exc)

    return ToolResponse(content=json.dumps(
        [{"title": "No results", "url": "", "content": f"Search returned no results for: {query}"}]
    ))


async def search_news(query: str, max_results: int = 5) -> ToolResponse:
    """Search recent news articles about a topic.

    Better than web_search for current events, recent developments,
    and time-sensitive information. Returns articles from the last few days.

    Args:
        query: News search query (2-6 keywords).
        max_results: Number of articles to return.

    Returns:
        JSON list of {title, url, content, date, source}.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(_executor, _ddg_news, query, max_results)
        if results:
            return ToolResponse(content=json.dumps(results, ensure_ascii=False))
    except Exception as exc:
        logger.warning("News search failed: %s", exc)

    return ToolResponse(content=json.dumps(
        [{"title": "No news results", "url": "", "content": f"No news found for: {query}"}]
    ))


async def quick_answer(query: str) -> ToolResponse:
    """Get a quick factual answer (like a calculator, definition, or conversion).

    Uses DuckDuckGo instant answers. Good for:
    - Definitions ("define machine learning")
    - Simple facts ("population of India")
    - Calculations, conversions

    Args:
        query: A factual question or lookup.

    Returns:
        JSON with the instant answer, or empty if none available.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(_executor, _ddg_quick, query)
        if results:
            return ToolResponse(content=json.dumps(results, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Quick answer failed: %s", exc)

    return ToolResponse(content=json.dumps(
        [{"title": "No instant answer", "url": "", "content": "No instant answer available. Try web_search instead."}]
    ))


async def _tavily_search(query: str, max_results: int, api_key: str) -> ToolResponse:
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": max_results,
                  "include_raw_content": False, "search_depth": "advanced"},
        )
        resp.raise_for_status()
        data = resp.json()
    results = [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in data.get("results", [])
    ]
    return ToolResponse(content=json.dumps(results, ensure_ascii=False))
