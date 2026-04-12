"""OpenAI embeddings helper for vector search."""

from __future__ import annotations

import os

import httpx

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


async def embed_text(text: str) -> list[float]:
    """Generate an embedding vector for a text string using OpenAI.

    Args:
        text: The text to embed (truncated to ~8000 tokens internally).

    Returns:
        List of floats (1536 dimensions for text-embedding-3-small).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    # Truncate to avoid token limits (~8000 tokens ≈ 32000 chars)
    text = text[:32000]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": text,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return data["data"][0]["embedding"]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors (same order as input).
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    truncated = [t[:32000] for t in texts]

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": EMBEDDING_MODEL,
                "input": truncated,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    # Sort by index to maintain order
    sorted_data = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in sorted_data]
