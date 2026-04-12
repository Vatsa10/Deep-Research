"""Unpaywall API wrapper for finding legal open-access versions of papers."""

from __future__ import annotations

import os

import httpx

UNPAYWALL_API = "https://api.unpaywall.org/v2"


async def find_open_access(doi: str) -> dict:
    """Find a legal open-access version of a paywalled paper via Unpaywall.

    Free API, 100K calls/day. Covers 30M+ articles.

    Args:
        doi: The DOI of the paper (e.g., "10.1038/s41586-024-07487-w").

    Returns:
        Dict with: doi, title, is_oa, oa_url, oa_type, journal, year.
        If no open access version found, oa_url will be empty.
    """
    email = os.environ.get("UNPAYWALL_EMAIL", "research@example.com")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{UNPAYWALL_API}/{doi}",
            params={"email": email},
        )

        if resp.status_code == 404:
            return {
                "doi": doi,
                "title": "",
                "is_oa": False,
                "oa_url": "",
                "oa_type": "",
                "journal": "",
                "year": None,
            }

        resp.raise_for_status()
        data = resp.json()

    best_location = data.get("best_oa_location") or {}

    return {
        "doi": doi,
        "title": data.get("title", ""),
        "is_oa": data.get("is_oa", False),
        "oa_url": best_location.get("url_for_pdf", "")
        or best_location.get("url", ""),
        "oa_type": best_location.get("host_type", ""),
        "journal": data.get("journal_name", ""),
        "year": data.get("year"),
    }


async def resolve_doi_urls(dois: list[str]) -> list[dict]:
    """Batch resolve multiple DOIs to open-access URLs.

    Args:
        dois: List of DOI strings.

    Returns:
        List of results from find_open_access for each DOI.
    """
    import asyncio

    tasks = [find_open_access(doi) for doi in dois]
    return await asyncio.gather(*tasks, return_exceptions=True)
