"""Web content extraction tool using httpx + trafilatura."""

from __future__ import annotations

import httpx
import trafilatura


async def fetch_url(url: str, max_words: int = 4000) -> dict:
    """Fetch and extract the main text content from a URL.

    Uses trafilatura for clean article extraction, stripping
    navigation, ads, and boilerplate.

    Args:
        url: The URL to fetch content from.
        max_words: Maximum words to return (truncates beyond this).

    Returns:
        Dict with keys: url, title, content, word_count.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DeepResearchBot/1.0; "
            "+https://github.com/deep-research)"
        ),
    }

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=20.0
    ) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    content = trafilatura.extract(
        html,
        include_links=True,
        include_tables=True,
        output_format="txt",
        favor_precision=True,
    )

    title = trafilatura.extract(html, output_format="xmltei")
    if title and "<title>" in title:
        title = title.split("<title>")[1].split("</title>")[0].strip()
    else:
        title = url

    content = content or ""
    words = content.split()
    word_count = len(words)

    if word_count > max_words:
        content = " ".join(words[:max_words]) + "\n\n[...truncated]"

    return {
        "url": url,
        "title": title,
        "content": content,
        "word_count": min(word_count, max_words),
    }
