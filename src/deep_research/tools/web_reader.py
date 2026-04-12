"""Content extraction from any URL — multi-strategy, resilient, auto-detecting.

Extraction chain (tries in order until one works):
1. trafilatura's built-in fetcher (handles cookies, redirects, retries)
2. httpx with browser headers
3. Structured data from meta tags / JSON-LD
4. Web archive (Wayback Machine) snapshot
5. Specialized extractors (YouTube, PDF, GitHub)
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs, urljoin

import httpx
import trafilatura
from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_cache: dict[str, dict] = {}


async def fetch_url(url: str, max_words: int = 4000) -> ToolResponse:
    """Fetch and extract the main content from any URL.

    Tries multiple extraction strategies to handle blocked sites,
    paywalls, login walls, and JS-rendered pages.

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
        logger.warning("All strategies failed for %s: %s", url, exc)
        result = _error_result(url, str(exc))

    _cache[url] = result
    return ToolResponse(content=json.dumps(result, ensure_ascii=False))


async def crawl_links(url: str, max_links: int = 10) -> ToolResponse:
    """Extract all links from a page for discovering related content.

    Args:
        url: The page URL to extract links from.
        max_links: Maximum number of links to return.

    Returns:
        JSON list of {text, url} for each link found.
    """
    try:
        html = await _fetch_html(url)
        links = _extract_all_links(html, url)[:max_links]
        return ToolResponse(content=json.dumps(links, ensure_ascii=False))
    except Exception as exc:
        return ToolResponse(content=json.dumps(
            [{"text": "Failed to crawl", "url": url, "error": str(exc)}]
        ))


# ── Router ────────────────────────────────────────────────────────────


async def _route_and_extract(url: str, max_words: int) -> dict:
    if _is_youtube(url):
        return await _extract_youtube(url, max_words)
    if _is_pdf(url):
        return await _extract_pdf(url, max_words)
    if _is_github(url):
        return await _extract_github(url, max_words)
    return await _extract_with_fallbacks(url, max_words)


async def _extract_with_fallbacks(url: str, max_words: int) -> dict:
    """Try every extraction strategy in order until one works."""

    # Strategy 1: trafilatura's own fetcher — it handles cookies,
    # redirects, retries, and many anti-bot measures internally
    try:
        result = await _extract_via_trafilatura_fetcher(url, max_words)
        if result["word_count"] > 50:
            return result
    except Exception as exc:
        logger.debug("trafilatura fetcher failed for %s: %s", url, exc)

    # Strategy 2: httpx with full browser headers
    try:
        result = await _extract_direct(url, max_words)
        if result["word_count"] > 50:
            return result
    except Exception as exc:
        logger.debug("Direct fetch failed for %s: %s", url, exc)

    # Strategy 3: httpx with Safari user-agent (some sites treat Safari differently)
    try:
        safari_headers = {
            **_HEADERS,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
            ),
        }
        result = await _extract_direct(url, max_words, headers=safari_headers)
        if result["word_count"] > 50:
            return result
    except Exception:
        pass

    # Strategy 4: Structured data (meta tags + JSON-LD) — works even
    # behind login walls since sites expose these for social sharing
    try:
        result = await _extract_structured_data(url, max_words)
        if result["word_count"] > 20:
            return result
    except Exception:
        pass

    # Strategy 5: Wayback Machine — if the page exists in the archive
    try:
        result = await _extract_via_wayback(url, max_words)
        if result["word_count"] > 50:
            return result
    except Exception:
        pass

    return _error_result(url, "Content could not be extracted with any strategy")


# ── Extractors ────────────────────────────────────────────────────────


def _trafilatura_fetch_sync(url: str, max_words: int) -> dict:
    """Use trafilatura's built-in fetcher (sync, runs in thread pool).

    trafilatura.fetch_url handles:
    - Cookies and sessions
    - Retries with backoff
    - Decompression
    - Many anti-bot measures
    """
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return _error_result(url, "trafilatura fetch returned empty")

    content = trafilatura.extract(
        downloaded,
        include_links=True,
        include_tables=True,
        output_format="txt",
        favor_precision=True,
    ) or ""

    title = trafilatura.extract(downloaded, output_format="xmltei")
    if title and "<title>" in title:
        title = title.split("<title>")[1].split("</title>")[0].strip()
    else:
        # Fallback: extract from HTML directly
        m = re.search(r"<title[^>]*>([^<]+)</title>", downloaded, re.IGNORECASE)
        title = m.group(1).strip() if m else url

    return _truncate(url, title, content, max_words, "web")


async def _extract_via_trafilatura_fetcher(url: str, max_words: int) -> dict:
    """Run trafilatura's fetcher in a thread pool (it's synchronous)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _trafilatura_fetch_sync, url, max_words)


async def _extract_direct(url: str, max_words: int, headers: dict | None = None) -> dict:
    """Direct httpx fetch + trafilatura extraction."""
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
    """Extract from meta tags and JSON-LD — works behind login walls."""
    html = await _fetch_html(url)

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

    content = description
    json_ld = _extract_json_ld(html)
    if json_ld:
        for key in ("articleBody", "description", "text", "abstract"):
            if key in json_ld and len(str(json_ld[key])) > len(content):
                content = str(json_ld[key])

    body = trafilatura.extract(html, output_format="txt") or ""
    if len(body) > len(content):
        content = body

    return _truncate(url, title, content, max_words, "structured")


async def _extract_via_wayback(url: str, max_words: int) -> dict:
    """Fetch from the Wayback Machine (Internet Archive)."""
    api_url = f"https://archive.org/wayback/available?url={url}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(api_url)
        if resp.status_code != 200:
            return _error_result(url, "Wayback API unavailable")

        data = resp.json()
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if not snapshot or not snapshot.get("available"):
            return _error_result(url, "No Wayback snapshot available")

        archive_url = snapshot["url"]
        resp = await client.get(archive_url, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text

    content = trafilatura.extract(html, output_format="txt") or ""
    title = _extract_title(html, url)
    return _truncate(url, f"[Archive] {title}", content, max_words, "archived")


async def _extract_youtube(url: str, max_words: int) -> dict:
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
    try:
        import pymupdf
    except ImportError:
        return _error_result(url, "pymupdf not installed")
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()
    doc = pymupdf.open(stream=resp.content, filetype="pdf")
    title = doc.metadata.get("title", "") or url.split("/")[-1]
    pages = [page.get_text() for page in doc]
    doc.close()
    return _truncate(url, title, "\n\n".join(pages), max_words, "pdf")


async def _extract_github(url: str, max_words: int) -> dict:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return await _extract_via_trafilatura_fetcher(url, max_words)

    owner, repo = parts[0], parts[1]
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        if len(parts) > 3 and parts[2] in ("blob", "tree"):
            branch, fp = parts[3], "/".join(parts[4:])
            raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fp}"
            resp = await client.get(raw)
            if resp.status_code == 200:
                return _truncate(url, f"{owner}/{repo}/{fp}", resp.text, max_words, "github")

        api = f"https://api.github.com/repos/{owner}/{repo}"
        resp = await client.get(api, headers={"Accept": "application/vnd.github.v3+json"})
        info, title = "", f"{owner}/{repo}"
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

        for branch in ("main", "master"):
            r = await client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md")
            if r.status_code == 200:
                return _truncate(url, title, info + r.text, max_words, "github")

        return _truncate(url, title, info or "README not found", max_words, "github")


# ── Helpers ───────────────────────────────────────────────────────────


async def _fetch_html(url: str) -> str:
    """Fetch raw HTML from a URL with browser headers."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        resp = await client.get(url, headers=_HEADERS)
        return resp.text


def _truncate(url: str, title: str, content: str, max_words: int, source_type: str) -> dict:
    words = content.split()
    wc = len(words)
    if wc > max_words:
        content = " ".join(words[:max_words]) + "\n\n[...truncated]"
    return {"url": url, "title": title, "content": content, "word_count": min(wc, max_words), "source_type": source_type}


def _error_result(url: str, msg: str) -> dict:
    return {"url": url, "title": url, "content": msg, "word_count": 0, "source_type": "error"}


def _is_youtube(url: str) -> bool:
    return any(d in url for d in ("youtube.com/watch", "youtu.be/", "youtube.com/shorts"))


def _is_pdf(url: str) -> bool:
    lower = url.lower().split("?")[0]
    return lower.endswith(".pdf") or "/pdf/" in lower


def _is_github(url: str) -> bool:
    return "github.com" in urlparse(url).netloc


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
    links, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>', html, re.IGNORECASE):
        href, text = m.group(1).strip(), m.group(2).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        full = urljoin(base_url, href)
        if full not in seen:
            seen.add(full)
            links.append({"text": text or full, "url": full})
    return links
