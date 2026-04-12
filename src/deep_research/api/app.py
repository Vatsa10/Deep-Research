"""FastAPI application for the deep research service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize AgentScope on startup."""
    import agentscope

    agentscope.init(project="deep-research")
    yield


app = FastAPI(
    title="Deep Research Service",
    description="Multi-agent deep research with async DAG execution",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
