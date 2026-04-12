"""Fact-checking tool: claim extraction, cross-source verification, and citation validation."""

from __future__ import annotations

import asyncio
import re

import httpx


async def verify_url(url: str) -> str:
    """Check if a URL is reachable. Returns 'verified', 'dead', or 'unresolvable'."""
    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True
        ) as client:
            resp = await client.head(url)
            if resp.status_code < 400:
                return "verified"
            # Some servers reject HEAD — try GET
            resp = await client.get(url, headers={"Range": "bytes=0-0"})
            return "verified" if resp.status_code < 400 else "dead"
    except (httpx.HTTPError, httpx.InvalidURL):
        return "dead"
    except Exception:
        return "unresolvable"


def extract_citations_from_markdown(report: str) -> list[dict]:
    """Extract all markdown links [text](url) from a report.

    Returns list of dicts with: text, url, line_number.
    """
    citations = []
    for i, line in enumerate(report.split("\n"), 1):
        for match in re.finditer(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line):
            citations.append({
                "text": match.group(1),
                "url": match.group(2),
                "line_number": i,
            })
    return citations


async def verify_all_citations(report: str) -> dict:
    """Verify all citations in a markdown report.

    Args:
        report: Markdown text containing [text](url) citations.

    Returns:
        Dict with: total, verified, dead, unresolvable, and details list.
    """
    citations = extract_citations_from_markdown(report)

    if not citations:
        return {
            "total": 0,
            "verified": 0,
            "dead": 0,
            "unresolvable": 0,
            "details": [],
        }

    # Deduplicate URLs for verification
    unique_urls = list({c["url"] for c in citations})
    tasks = [verify_url(url) for url in unique_urls]
    results = await asyncio.gather(*tasks)
    url_status = dict(zip(unique_urls, results))

    # Map back to citations
    details = []
    for c in citations:
        status = url_status.get(c["url"], "unresolvable")
        details.append({
            "text": c["text"],
            "url": c["url"],
            "line_number": c["line_number"],
            "status": status,
        })

    verified = sum(1 for d in details if d["status"] == "verified")
    dead = sum(1 for d in details if d["status"] == "dead")
    unresolvable = sum(1 for d in details if d["status"] == "unresolvable")

    return {
        "total": len(details),
        "verified": verified,
        "dead": dead,
        "unresolvable": unresolvable,
        "details": details,
        "dead_links": [d["url"] for d in details if d["status"] == "dead"],
        "verified_links": [d["url"] for d in details if d["status"] == "verified"],
    }


def find_unsupported_claims(
    report: str,
    source_contents: dict[str, str],
) -> list[str]:
    """Identify claims in the report that aren't backed by any source content.

    This is a heuristic check: extracts sentences with statistical claims
    (numbers, percentages, dollar amounts) and checks whether similar
    text appears in any source.

    Args:
        report: The synthesized markdown report.
        source_contents: Dict mapping source URLs to their extracted text.

    Returns:
        List of claim sentences that appear unsupported.
    """
    # Extract sentences with numbers/statistics
    stat_pattern = re.compile(
        r'[^.]*(?:\d+%|\$\d+|\d+\.\d+|\d{2,}(?:\s+(?:million|billion|trillion|percent)))[^.]*\.',
        re.IGNORECASE,
    )

    claims = stat_pattern.findall(report)
    all_source_text = " ".join(source_contents.values()).lower()

    unsupported = []
    for claim in claims:
        # Extract the key numbers from the claim
        numbers = re.findall(r'\d+\.?\d*', claim)
        # Check if at least one number from the claim appears in sources
        if numbers and not any(n in all_source_text for n in numbers):
            unsupported.append(claim.strip())

    return unsupported
