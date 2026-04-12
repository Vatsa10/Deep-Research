"""Content extraction from any URL — resilient, multi-strategy, auto-detecting."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse, parse_qs, urljoin

import httpx
import trafilatura
from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
}

# Cache to avoid re-fetching the same URL in a single session
_cache: dict[str, dict] = {}


async def fetch_url(url: str, max_words: int = 4000) -> ToolResponse:
    """Fetch and extract the main content from any URL.

    Automatically handles web pages, PDFs, YouTube, GitHub, LinkedIn,
    and other platforms. Retries with different strategies if blocked.

    Args:
        url: Any URL to extract content from.
        max_words: Maximum words to return (default 4000).

    Returns:
        JSON with url, title, content, word_count, source_type.
    """
    url = url.strip()

    if url in _cache:
        return ToolResponse(content=json.dumps(_cache[url], ensure_ascii=False))

    try:
        result = await _route_and_extract(url, max_words)
    except Exception as exc:
        logger.warning("All extraction strategies failed for %s: %s", url, exc)
        result = _error_result(url, str(exc))

    _cache[url] = result
    return ToolResponse(content=json.dumps(result, ensure_ascii=False))


async def crawl_links(url: str, max_links: int = 10) -> ToolResponse:
    """Extract all links from a page, useful for discovering related content.

    Use this when you want to find related pages, sub-pages, or references
    within a website you've already read.

    Args:
        url: The page URL to extract links from.
        max_links: Maximum number of links to return.

    Returns:
        JSON list of {text, url} for each link found on the page.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            html = resp.text

        links = _extract_all_links(html, url)[:max_links]
        return ToolResponse(content=json.dumps(links, ensure_ascii=False))
    except Exception as exc:
        return ToolResponse(content=json.dumps(
            [{"text": "Failed to crawl", "url": url, "error": str(exc)}]
        ))


# ── Router ────────────────────────────────────────────────────────────


async def _route_and_extract(url: str, max_words: int) -> dict:
    """Route URL to the best extractor."""
    if _is_youtube(url):
        return await _extract_youtube(url, max_words)
    if _is_pdf(url):
        return await _extract_pdf(url, max_words)
    if _is_github(url):
        return await _extract_github(url, max_words)

    # For everything else (including LinkedIn, Twitter, etc.):
    # try multiple strategies in order
    return await _extract_with_fallbacks(url, max_words)


async def _extract_with_fallbacks(url: str, max_words: int) -> dict:
    """Try multiple extraction strategies — resilient to blocks and JS walls."""

    # Strategy 1: Direct fetch + trafilatura (works for most sites)
    try:
        result = await _extract_direct(url, max_words)
        if result["word_count"] > 50:
            return result
    except Exception:
        pass

    # Strategy 2: Try with different Accept header (some sites serve
    # different content to different clients)
    try:
        result = await _extract_direct(url, max_words, headers={
            **_HEADERS,
            "Accept": "text/html",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
            ),
        })
        if result["word_count"] > 50:
            return result
    except Exception:
        pass

    # Strategy 3: Meta tags / JSON-LD extraction (works for LinkedIn,
    # Twitter cards, etc. even behind login walls)
    try:
        result = await _extract_structured_data(url, max_words)
        if result["word_count"] > 20:
            return result
    except Exception:
        pass

    # Strategy 4: Google cache (last resort for blocked pages)
    try:
        result = await _extract_via_cache(url, max_words)
        if result["word_count"] > 50:
            return result
    except Exception:
        pass

    return _error_result(url, "Content could not be extracted with any strategy")


# ── Extractors ────────────────────────────────────────────────────────


async def _extract_direct(url: str, max_words: int, headers: dict | None = None) -> dict:
    """Direct HTTP fetch + trafilatura extraction."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers=headers or _HEADERS)
        resp.raise_for_status()
        html = resp.text

    content = trafilatura.extract(
        html, include_links=True, include_tables=True,
        output_format="txt", favor_precision=True,
    ) or ""

    title = _extract_title(html, url)
    return _truncate(url, title, content, max_words, "web")


async def _extract_structured_data(url: str, max_words: int) -> dict:
    """Extract from meta tags and JSON-LD — works even behind login walls."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        html = resp.text

    title = (
        _extract_meta(html, "og:title")
        or _extract_meta(html, "twitter:title")
        or _extract_meta(html, "title")
        or url
    )

    description = (
        _extract_meta(html, "og:description")
        or _extract_meta(html, "twitter:description")
        or _extract_meta(html, "description")
        or ""
    )

    # JSON-LD often has richer content
    json_ld = _extract_json_ld(html)
    content = description
    if json_ld:
        for key in ("articleBody", "description", "text", "abstract"):
            if key in json_ld and len(str(json_ld[key])) > len(content):
                content = str(json_ld[key])

    # Also try trafilatura as supplement
    body = trafilatura.extract(html, output_format="txt") or ""
    if len(body) > len(content):
        content = body

    return _truncate(url, title, content, max_words, "structured")


async def _extract_via_cache(url: str, max_words: int) -> dict:
    """Try to fetch a cached version of the page via Google Web Cache."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(cache_url, headers=_HEADERS)
        if resp.status_code != 200:
            return _error_result(url, "Cache not available")
        html = resp.text

    content = trafilatura.extract(html, output_format="txt") or ""
    title = _extract_title(html, url)
    return _truncate(url, f"[Cached] {title}", content, max_words, "cached")


async def _extract_youtube(url: str, max_words: int) -> dict:
    """Extract YouTube transcript."""
    video_id = _get_youtube_id(url)
    if not video_id:
        return _error_result(url, "Could not parse YouTube video ID")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        result = api.fetch(video_id)
        text = " ".join(snippet.text for snippet in result.snippets)
        title = await _get_youtube_title(video_id)
        return _truncate(url, title, text, max_words, "youtube")
    except ImportError:
        return _error_result(url, "youtube-transcript-api not installed")
    except Exception as exc:
        return _error_result(url, f"Transcript unavailable: {exc}")


async def _extract_pdf(url: str, max_words: int) -> dict:
    """Download and extract text from a PDF."""
    try:
        import pymupdf
    except ImportError:
        return _error_result(url, "pymupdf not installed")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
        pdf_bytes = resp.content

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    title = doc.metadata.get("title", "") or url.split("/")[-1]
    pages_text = [page.get_text() for page in doc]
    doc.close()

    return _truncate(url, title, "\n\n".join(pages_text), max_words, "pdf")


async def _extract_github(url: str, max_words: int) -> dict:
    """Extract GitHub repo info + README, or specific file content."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) < 2:
        return await _extract_direct(url, max_words)

    owner, repo = parts[0], parts[1]

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # Specific file
        if len(parts) > 3 and parts[2] in ("blob", "tree"):
            branch, file_path = parts[3], "/".join(parts[4:])
            raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
            resp = await client.get(raw, headers=_HEADERS)
            if resp.status_code == 200:
                return _truncate(url, f"{owner}/{repo}/{file_path}", resp.text, max_words, "github")

        # Repo overview
        api = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await client.get(api, headers={**_HEADERS, "Accept": "application/vnd.github.v3+json"})

        info = ""
        title = f"{owner}/{repo}"
        if resp.status_code == 200:
            d = resp.json()
            title = d.get("full_name", title)
            info = (
                f"Repository: {d.get('full_name', '')}\n"
                f"Description: {d.get('description', '')}\n"
                f"Stars: {d.get('stargazers_count', 0)} | Forks: {d.get('forks_count', 0)}\n"
                f"Language: {d.get('language', '?')} | Topics: {', '.join(d.get('topics', []))}\n"
                f"Updated: {d.get('updated_at', '')}\n\n"
            )

        # README
        for branch in ("main", "master"):
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"
            resp = await client.get(readme_url)
            if resp.status_code == 200:
                return _truncate(url, title, info + resp.text, max_words, "github")

        return _truncate(url, title, info or "README not found", max_words, "github")


# ── URL Detection ─────────────────────────────────────────────────────


def _is_youtube(url: str) -> bool:
    return any(d in url for d in ("youtube.com/watch", "youtu.be/", "youtube.com/shorts"))


def _is_pdf(url: str) -> bool:
    lower = url.lower().split("?")[0]
    return lower.endswith(".pdf") or "/pdf/" in lower


def _is_github(url: str) -> bool:
    return "github.com" in urlparse(url).netloc


# ── Helpers ───────────────────────────────────────────────────────────


def _truncate(url: str, title: str, content: str, max_words: int, source_type: str) -> dict:
    words = content.split()
    wc = len(words)
    if wc > max_words:
        content = " ".join(words[:max_words]) + "\n\n[...truncated]"
    return {"url": url, "title": title, "content": content, "word_count": min(wc, max_words), "source_type": source_type}


def _error_result(url: str, msg: str) -> dict:
    return {"url": url, "title": url, "content": msg, "word_count": 0, "source_type": "error"}


def _get_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/")
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.search(r"/shorts/([^/?]+)", parsed.path)
    return m.group(1) if m else None


async def _get_youtube_title(video_id: str) -> str:
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


def _extract_title(html: str, fallback: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return m.group(1).strip() if m else fallback


def _extract_meta(html: str, name: str) -> str:
    for pat in [
        rf'<meta[^>]+(?:name|property)="{name}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="{name}"',
    ]:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1)
    if name == "title":
        return _extract_title(html, "")
    return ""


def _extract_json_ld(html: str) -> dict | None:
    m = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m:
        try:
            data = json.loads(m.group(1))
            return data[0] if isinstance(data, list) else data
        except Exception:
            pass
    return None


def _extract_all_links(html: str, base_url: str) -> list[dict]:
    """Extract all <a> links from HTML, resolving relative URLs."""
    links = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>', html, re.IGNORECASE):
        href, text = m.group(1).strip(), m.group(2).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        full_url = urljoin(base_url, href)
        if full_url not in seen:
            seen.add(full_url)
            links.append({"text": text or full_url, "url": full_url})
    return links
