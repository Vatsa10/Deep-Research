"""Tests for web search and web reader tools."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_web_search_returns_results():
    """web_search should return a list of result dicts."""
    mock_response = {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com/test",
                "content": "Test content about the query.",
                "score": 0.95,
            },
            {
                "title": "Another Result",
                "url": "https://example.com/other",
                "content": "More content.",
                "score": 0.85,
            },
        ]
    }

    with patch("deep_research.tools.web_search.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)

        with patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"}):
            from deep_research.tools.web_search import web_search

            results = await web_search("quantum computing", max_results=2)

    assert len(results) == 2
    assert results[0]["title"] == "Test Result"
    assert results[0]["url"] == "https://example.com/test"
    assert results[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_web_search_no_api_key():
    """web_search should return error when API key is missing."""
    with patch.dict("os.environ", {}, clear=True):
        # Need to reimport to pick up the env change
        import importlib
        import deep_research.tools.web_search as ws_mod

        importlib.reload(ws_mod)
        results = await ws_mod.web_search("test query")

    assert len(results) == 1
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_fetch_url_extracts_content():
    """fetch_url should extract text content from HTML."""
    sample_html = """
    <html>
    <head><title>Test Page</title></head>
    <body>
    <article>
    <h1>Main Content</h1>
    <p>This is the main article content that should be extracted.</p>
    </article>
    </body>
    </html>
    """

    with patch("deep_research.tools.web_reader.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_resp = MagicMock()
        mock_resp.text = sample_html
        mock_resp.raise_for_status = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_resp)

        from deep_research.tools.web_reader import fetch_url

        result = await fetch_url("https://example.com/test")

    assert result["url"] == "https://example.com/test"
    assert isinstance(result["content"], str)
    assert isinstance(result["word_count"], int)
