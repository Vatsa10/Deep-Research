"""Research memory: store and search past research via Qdrant."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from .client import get_qdrant, RESEARCH_MEMORY_COLLECTION, SOURCE_KNOWLEDGE_COLLECTION
from .embeddings import embed_text

logger = logging.getLogger(__name__)


async def store_research_memory(
    session_id: str,
    user_id: str,
    query: str,
    distilled_summary: str,
    domain: str = "general",
    query_type: str = "exploratory",
) -> None:
    """Store a completed research session in vector memory.

    The embedding is generated from query + summary for semantic retrieval.
    """
    try:
        text = f"{query}\n\n{distilled_summary}"
        vector = await embed_text(text)

        client = get_qdrant()
        client.upsert(
            collection_name=RESEARCH_MEMORY_COLLECTION,
            points=[
                PointStruct(
                    id=session_id,
                    vector=vector,
                    payload={
                        "user_id": user_id,
                        "query": query,
                        "distilled_summary": distilled_summary[:1000],
                        "domain": domain,
                        "query_type": query_type,
                        "session_id": session_id,
                    },
                )
            ],
        )
        logger.info("Stored research memory: %s", session_id)
    except Exception:
        logger.warning("Failed to store research memory", exc_info=True)


async def search_similar_research(
    query: str,
    user_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Find similar past research sessions.

    Args:
        query: The search query to find similar research.
        user_id: Optional filter to only search this user's research.
        top_k: Number of results to return.

    Returns:
        List of dicts with: session_id, query, distilled_summary, score.
    """
    try:
        vector = await embed_text(query)
        client = get_qdrant()

        query_filter = None
        if user_id:
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )

        results = client.query_points(
            collection_name=RESEARCH_MEMORY_COLLECTION,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
        ).points

        return [
            {
                "session_id": r.payload.get("session_id", ""),
                "query": r.payload.get("query", ""),
                "distilled_summary": r.payload.get("distilled_summary", ""),
                "domain": r.payload.get("domain", ""),
                "score": r.score,
            }
            for r in results
        ]
    except Exception:
        logger.warning("Failed to search similar research", exc_info=True)
        return []


async def store_source_knowledge(
    session_id: str,
    url: str,
    title: str,
    content_snippet: str,
    source_type: str = "unknown",
    credibility_tier: str = "tier3",
) -> None:
    """Store a source's content in vector memory for RAG."""
    try:
        vector = await embed_text(content_snippet)
        point_id = str(uuid.uuid4())

        client = get_qdrant()
        client.upsert(
            collection_name=SOURCE_KNOWLEDGE_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "session_id": session_id,
                        "url": url,
                        "title": title,
                        "source_type": source_type,
                        "credibility_tier": credibility_tier,
                        "content_snippet": content_snippet[:500],
                    },
                )
            ],
        )
    except Exception:
        logger.warning("Failed to store source knowledge", exc_info=True)


async def search_source_knowledge(
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Search past source content for RAG augmentation."""
    try:
        vector = await embed_text(query)
        client = get_qdrant()

        results = client.query_points(
            collection_name=SOURCE_KNOWLEDGE_COLLECTION,
            query=vector,
            limit=top_k,
        ).points

        return [
            {
                "url": r.payload.get("url", ""),
                "title": r.payload.get("title", ""),
                "content_snippet": r.payload.get("content_snippet", ""),
                "source_type": r.payload.get("source_type", ""),
                "credibility_tier": r.payload.get("credibility_tier", ""),
                "score": r.score,
            }
            for r in results
        ]
    except Exception:
        logger.warning("Failed to search source knowledge", exc_info=True)
        return []
