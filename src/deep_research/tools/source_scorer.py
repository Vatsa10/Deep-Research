"""Source credibility scoring based on domain authority, source type, and recency."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Domain authority tiers — higher tier = more credible
TIER1_DOMAINS = [
    ".edu", ".gov", ".gov.uk", ".ac.uk",
    "nature.com", "science.org", "sciencedirect.com",
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "springer.com",
    "wiley.com", "cell.com", "thelancet.com", "nejm.org",
    "ieee.org", "acm.org", "pnas.org",
]

TIER2_DOMAINS = [
    ".org",
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "nytimes.com", "washingtonpost.com", "theguardian.com",
    "economist.com", "ft.com", "bloomberg.com",
    "techcrunch.com", "arstechnica.com", "wired.com",
    "docs.python.org", "developer.mozilla.org", "learn.microsoft.com",
]

LOW_CREDIBILITY_DOMAINS = [
    "medium.com", "reddit.com", "quora.com", "blogspot.com",
    "wordpress.com", "tumblr.com", "substack.com",
    "yahoo.com/answers", "answers.com",
    "pinterest.com", "facebook.com", "twitter.com", "x.com",
]

# Source type detection patterns
ACADEMIC_INDICATORS = [
    "doi.org", "arxiv.org", "pubmed", "scholar.google",
    "semanticscholar.org", "jstor.org", "researchgate.net",
    "sciencedirect.com", "springer.com", "wiley.com",
]

GOV_INDICATORS = [".gov", ".gov.uk", ".gov.au", ".gc.ca"]

NEWS_MAJOR_INDICATORS = [
    "reuters.com", "apnews.com", "bbc.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "bloomberg.com",
]


def classify_source_type(url: str) -> str:
    """Classify a URL into a source type category."""
    url_lower = url.lower()

    if any(ind in url_lower for ind in ACADEMIC_INDICATORS):
        return "academic"
    if any(ind in url_lower for ind in GOV_INDICATORS):
        return "government"
    if any(ind in url_lower for ind in NEWS_MAJOR_INDICATORS):
        return "news_major"

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if any(d in domain for d in LOW_CREDIBILITY_DOMAINS):
        return "blog" if "medium" in domain or "substack" in domain else "forum"
    if "news" in domain or "press" in domain:
        return "news_other"
    if "docs." in domain or "developer." in domain or "learn." in domain:
        return "documentation"

    return "unknown"


def get_credibility_tier(url: str) -> str:
    """Determine the credibility tier of a URL."""
    url_lower = url.lower()
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    for pattern in TIER1_DOMAINS:
        if pattern.startswith("."):
            if domain.endswith(pattern):
                return "tier1"
        elif pattern in domain:
            return "tier1"

    for pattern in TIER2_DOMAINS:
        if pattern.startswith("."):
            if domain.endswith(pattern):
                return "tier2"
        elif pattern in domain:
            return "tier2"

    for pattern in LOW_CREDIBILITY_DOMAINS:
        if pattern in domain:
            return "low"

    return "tier3"


TIER_SCORES = {"tier1": 0.95, "tier2": 0.75, "tier3": 0.5, "low": 0.2}


def score_source(
    url: str,
    content: str = "",
    publication_date: str = "",
    temporal_scope: str = "",
) -> dict:
    """Score a source's credibility.

    Args:
        url: The source URL.
        content: Extracted text content (used for reference density analysis).
        publication_date: ISO date string of when the source was published.
        temporal_scope: The research's temporal scope (e.g., "2024-2026").

    Returns:
        Dict with credibility_score, source_type, credibility_tier,
        domain_authority, is_peer_reviewed, recency_note.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    source_type = classify_source_type(url)
    tier = get_credibility_tier(url)
    base_score = TIER_SCORES.get(tier, 0.5)

    # Peer review detection
    is_peer_reviewed = source_type == "academic" and tier == "tier1"

    # Recency adjustment
    recency_note = ""
    if publication_date:
        try:
            pub_date = datetime.fromisoformat(publication_date.split("T")[0])
            age_days = (datetime.now() - pub_date).days
            if age_days < 180:
                base_score = min(1.0, base_score + 0.05)
            elif age_days > 730:  # > 2 years
                base_score = max(0.1, base_score - 0.1)
                recency_note = f"Source is {age_days // 365} years old"
        except (ValueError, TypeError):
            pass

    # Reference density bonus — content with many citations is more credible
    if content:
        ref_count = len(re.findall(r'\[\d+\]|\(\d{4}\)|doi\.org|https?://', content[:5000]))
        if ref_count > 10:
            base_score = min(1.0, base_score + 0.05)

    return {
        "credibility_score": round(base_score, 2),
        "source_type": source_type,
        "credibility_tier": tier,
        "domain_authority": domain,
        "is_peer_reviewed": is_peer_reviewed,
        "recency_note": recency_note,
    }
