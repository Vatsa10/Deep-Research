"""Smart content extraction — auto-detects URL type and uses the right extractor.

Supports: regular web pages, YouTube transcripts, PDFs, LinkedIn profiles,
GitHub repos/files. Falls back gracefully when extraction fails.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse, parse_qs

import httpx
import trafilatura
from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

# Browser-like headers to bypass basic bot detection
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def fetch_url(url: str, max_words: int = 4000) -> ToolResponse:
    """Fetch and extract content from any URL.

    Auto-detects the URL type and routes to the appropriate extractor:
    - YouTube → transcript extraction
    - PDF → text extraction via PyMuPDF
    - LinkedIn → profile/post scraping with browser headers
    - GitHub → README/file content via raw API
    - Everything else → trafilatura article extraction

    Args:
        url: The URL to fetch content from.
        max_words: Maximum words to return (truncates beyond this).

    Returns:
        ToolResponse with JSON string containing url, title, content, word_count, source_type.
    """
    url = url.strip()

    try:
        if _is_youtube(url):
            result = await _extract_youtube(url, max_words)
        elif _is_pdf(url):
            result = await _extract_pdf(url, max_words)
        elif _is_linkedin(url):
            result = await _extract_linkedin(url, max_words)
        elif _is_github(url):
            result = await _extract_github(url, max_words)
        else:
            result = await _extract_web(url, max_words)
    except Exception as exc:
        logger.warning("Extraction failed for %s: %s", url, exc)
        result = {
            "url": url,
            "title": url,
            "content": f"Failed to extract content: {exc}",
            "word_count": 0,
            "source_type": "error",
        }

    return ToolResponse(content=json.dumps(result, ensure_ascii=False))


# ── URL Detection ─────────────────────────────────────────────────────


def _is_youtube(url: str) -> bool:
    return any(d in url for d in ("youtube.com/watch", "youtu.be/", "youtube.com/shorts"))


def _is_pdf(url: str) -> bool:
    return url.lower().endswith(".pdf") or "/pdf/" in url.lower()


def _is_linkedin(url: str) -> bool:
    return "linkedin.com" in url


def _is_github(url: str) -> bool:
    return "github.com" in url


# ── Extractors ────────────────────────────────────────────────────────


async def _extract_web(url: str, max_words: int) -> dict:
    """Standard web page extraction via trafilatura."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers=_HEADERS)
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
    return _truncate(url, title, content, max_words, "web")


async def _extract_youtube(url: str, max_words: int) -> dict:
    """Extract YouTube video transcript."""
    video_id = _get_youtube_id(url)
    if not video_id:
        return {"url": url, "title": url, "content": "Could not parse YouTube video ID", "word_count": 0, "source_type": "youtube"}

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        result = api.fetch(video_id)
        text = " ".join(snippet.text for snippet in result.snippets)

        title = await _get_youtube_title(video_id)

        return _truncate(url, f"[YouTube] {title}", text, max_words, "youtube")

    except ImportError:
        return {"url": url, "title": url, "content": "youtube-transcript-api not installed", "word_count": 0, "source_type": "youtube"}
    except Exception as exc:
        return {"url": url, "title": url, "content": f"Transcript unavailable: {exc}", "word_count": 0, "source_type": "youtube"}


async def _extract_pdf(url: str, max_words: int) -> dict:
    """Download and extract text from a PDF."""
    try:
        import pymupdf
    except ImportError:
        return {"url": url, "title": url, "content": "pymupdf not installed — cannot extract PDF", "word_count": 0, "source_type": "pdf"}

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        pdf_bytes = resp.content

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    title = doc.metadata.get("title", "") or url.split("/")[-1]

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()

    full_text = "\n\n".join(pages_text)
    return _truncate(url, f"[PDF] {title}", full_text, max_words, "pdf")


async def _extract_linkedin(url: str, max_words: int) -> dict:
    """Extract LinkedIn profile/post content.

    LinkedIn blocks most scrapers, so we use:
    1. Browser-like headers to get whatever public HTML is available
    2. Structured data extraction from JSON-LD / meta tags
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers={
            **_HEADERS,
            "Accept": "text/html,application/xhtml+xml",
        })
        html = resp.text

    # Try trafilatura first
    content = trafilatura.extract(html, include_links=True, output_format="txt") or ""

    # Extract structured data from meta tags (LinkedIn exposes these publicly)
    title = _extract_meta(html, "og:title") or _extract_meta(html, "title") or url
    description = _extract_meta(html, "og:description") or _extract_meta(html, "description") or ""

    if not content and description:
        content = description

    # Extract JSON-LD if available
    json_ld = _extract_json_ld(html)
    if json_ld:
        if "articleBody" in json_ld:
            content = json_ld["articleBody"]
        elif "description" in json_ld and len(json_ld["description"]) > len(content):
            content = json_ld["description"]

    if not content:
        content = "LinkedIn content could not be fully extracted (login wall). Available metadata: " + description

    return _truncate(url, f"[LinkedIn] {title}", content, max_words, "linkedin")


async def _extract_github(url: str, max_words: int) -> dict:
    """Extract GitHub repository README or file content via API.

    Uses GitHub's raw content URLs and API (no auth needed for public repos).
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(path_parts) < 2:
        return await _extract_web(url, max_words)  # not a valid repo URL

    owner, repo = path_parts[0], path_parts[1]

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # If URL points to a specific file (blob/tree path)
        if len(path_parts) > 3 and path_parts[2] in ("blob", "tree"):
            branch = path_parts[3]
            file_path = "/".join(path_parts[4:])
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
            resp = await client.get(raw_url, headers=_HEADERS)
            if resp.status_code == 200:
                return _truncate(url, f"[GitHub] {owner}/{repo}/{file_path}", resp.text, max_words, "github")

        # Get repo info via API
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await client.get(api_url, headers={**_HEADERS, "Accept": "application/vnd.github.v3+json"})

        repo_info = ""
        title = f"{owner}/{repo}"
        if resp.status_code == 200:
            data = resp.json()
            title = data.get("full_name", title)
            repo_info = (
                f"Repository: {data.get('full_name', '')}\n"
                f"Description: {data.get('description', '')}\n"
                f"Stars: {data.get('stargazers_count', 0)}\n"
                f"Forks: {data.get('forks_count', 0)}\n"
                f"Language: {data.get('language', 'Unknown')}\n"
                f"Topics: {', '.join(data.get('topics', []))}\n"
                f"Last updated: {data.get('updated_at', '')}\n\n"
            )

        # Get README
        readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
        resp = await client.get(readme_url, headers=_HEADERS)
        if resp.status_code != 200:
            # Try master branch
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
            resp = await client.get(readme_url, headers=_HEADERS)

        readme = resp.text if resp.status_code == 200 else "README not found."

        full_content = repo_info + readme
        return _truncate(url, f"[GitHub] {title}", full_content, max_words, "github")


# ── Helpers ───────────────────────────────────────────────────────────


def _truncate(url: str, title: str, content: str, max_words: int, source_type: str) -> dict:
    """Truncate content and build the result dict."""
    words = content.split()
    word_count = len(words)
    if word_count > max_words:
        content = " ".join(words[:max_words]) + "\n\n[...truncated]"
    return {
        "url": url,
        "title": title,
        "content": content,
        "word_count": min(word_count, max_words),
        "source_type": source_type,
    }


def _get_youtube_id(url: str) -> str | None:
    """Extract video ID from a YouTube URL."""
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/")
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    # /shorts/ID
    match = re.search(r"/shorts/([^/?]+)", parsed.path)
    if match:
        return match.group(1)
    return None


async def _get_youtube_title(video_id: str) -> str:
    """Get video title via oEmbed (free, no API key)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://www.youtube.com/oembed?url=https://youtube.com/watch?v={video_id}&format=json"
            )
            if resp.status_code == 200:
                return resp.json().get("title", video_id)
    except Exception:
        pass
    return video_id


def _extract_meta(html: str, name: str) -> str:
    """Extract content from a meta tag."""
    patterns = [
        rf'<meta[^>]+(?:name|property)="{name}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="{name}"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    # Try <title> tag
    if name == "title":
        match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_json_ld(html: str) -> dict | None:
    """Extract the first JSON-LD block from HTML."""
    match = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        try:
            import json as _json
            data = _json.loads(match.group(1))
            if isinstance(data, list):
                return data[0] if data else None
            return data
        except Exception:
            pass
    return None
