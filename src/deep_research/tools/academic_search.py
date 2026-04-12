"""Semantic Scholar API wrapper for academic paper search."""

from __future__ import annotations

import json

import httpx
from agentscope.tool import ToolResponse

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,citationCount,year,authors,openAccessPdf,externalIds,venue"


async def academic_search(
    query: str,
    max_results: int = 5,
    year_range: str = "",
) -> ToolResponse:
    """Search Semantic Scholar for academic papers.

    Free API, no auth needed. 200M+ papers indexed.

    Args:
        query: Search query string.
        max_results: Maximum papers to return (max 100).
        year_range: Optional year filter, e.g. "2023-2026".

    Returns:
        ToolResponse with JSON string of papers (title, abstract, url, authors, etc.).
    """
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": FIELDS,
    }
    if year_range:
        params["year"] = year_range

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/search",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for paper in data.get("data", []):
        authors = [a.get("name", "") for a in paper.get("authors", [])]
        external_ids = paper.get("externalIds", {}) or {}
        doi = external_ids.get("DOI", "")
        oa_pdf = paper.get("openAccessPdf") or {}

        results.append({
            "title": paper.get("title", ""),
            "abstract": (paper.get("abstract") or "")[:500],
            "url": f"https://api.semanticscholar.org/CorpusID:{paper.get('corpusId', '')}",
            "authors": authors[:5],
            "year": paper.get("year"),
            "citation_count": paper.get("citationCount", 0),
            "doi": doi,
            "open_access_url": oa_pdf.get("url", ""),
            "venue": paper.get("venue", ""),
            "source_type": "academic",
            "is_peer_reviewed": bool(paper.get("venue")),
        })

    results.sort(key=lambda x: x["citation_count"], reverse=True)

    return ToolResponse(content=json.dumps(results, ensure_ascii=False))
