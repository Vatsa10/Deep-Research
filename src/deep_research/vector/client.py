"""Qdrant client initialization and collection management."""

from __future__ import annotations

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None

RESEARCH_MEMORY_COLLECTION = "research_memory"
SOURCE_KNOWLEDGE_COLLECTION = "source_knowledge"
EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small


def get_qdrant() -> QdrantClient:
    """Get the Qdrant client (singleton)."""
    global _client
    if _client is None:
        raise RuntimeError("Qdrant not initialized. Call init_qdrant() first.")
    return _client


def init_qdrant() -> QdrantClient:
    """Initialize Qdrant client and create collections if needed."""
    global _client

    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    api_key = os.environ.get("QDRANT_API_KEY", "")

    if api_key:
        _client = QdrantClient(url=url, api_key=api_key)
    else:
        _client = QdrantClient(url=url)

    # Create collections if they don't exist
    _ensure_collection(
        RESEARCH_MEMORY_COLLECTION,
        "Stores completed research sessions for semantic search",
    )
    _ensure_collection(
        SOURCE_KNOWLEDGE_COLLECTION,
        "Stores extracted source content for RAG",
    )

    logger.info("Qdrant initialized: %s", url)
    return _client


def _ensure_collection(name: str, description: str) -> None:
    """Create a collection if it doesn't exist."""
    collections = _client.get_collections().collections
    if not any(c.name == name for c in collections):
        _client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created Qdrant collection: %s", name)


def close_qdrant() -> None:
    """Close the Qdrant client."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
