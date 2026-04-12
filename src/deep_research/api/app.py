"""FastAPI application for the deep research service."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .auth_routes import router as auth_router
from .share_routes import router as share_router
from .template_routes import router as template_router

load_dotenv()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize all services on startup."""
    import agentscope

    # 1. AgentScope
    agentscope.init(project="deep-research")

    # 2. Database (Turso/SQLite)
    from ..db.client import init_db, close_db
    from ..db.templates import seed_builtin_templates

    init_db()
    seed_builtin_templates()
    logger.info("Database initialized + templates seeded")

    # 3. Vector store (Qdrant) — optional, gracefully skip if unavailable
    try:
        from ..vector.client import init_qdrant, close_qdrant

        init_qdrant()
        logger.info("Qdrant vector store initialized")
    except Exception as exc:
        logger.warning("Qdrant not available (non-critical): %s", exc)

    yield

    # Cleanup
    close_db()
    try:
        close_qdrant()
    except Exception:
        pass


app = FastAPI(
    title="Deep Research Service",
    description="Multi-agent deep research with async DAG execution",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(auth_router)
app.include_router(router)
app.include_router(share_router)
app.include_router(template_router)
