# Deep Research

A multi-agent deep research service built with [AgentScope](https://github.com/agentscope-ai/agentscope). Submit a query, and a team of AI agents collaborates through an async DAG pipeline to produce a comprehensive, sourced research report.

This project was built as a hands-on way to learn AgentScope and understand how its agent abstractions, tool registration, message passing, and pipeline orchestration work in practice. Rather than running through tutorials, the goal was to build something real that exercises the framework's core concepts — and then push past them by implementing a custom DAG executor, Mixture-of-Experts routing, hybrid memory, and a resilient multi-strategy scraper.

## How It Works

```
                        +--- WebAgent_1 ---+
                        |  (autonomous:   |
                        |   search, read, |
                        |   crawl, fetch) |
User Query              +--- WebAgent_2 --+
    |                   |                 |
    v                   |     ...         |
Classifier --> Router --> Planner --+                +--> Synthesizer --> [Distiller] --> Critic --> Report
   (MoE)                              +--- WebAgent_N |                                        |
                                                      +                      +-- if gaps, re-plan --+
```

**Pipeline stages:**

1. **Query Classifier** (MoE) — A single cheap LLM call classifies the query as `simple`, `moderate`, or `complex`, and picks a domain (technical, medical, scientific, etc.)
2. **Router** — Based on the classification, selects which agents to skip, which models to use per agent (`gpt-4o-mini` vs `gpt-4o`), and how many iterations to allow
3. **Validator** *(skipped for simple queries)* — Checks the query premise for soundness; rejects nonsense, flags controversial assumptions
4. **Planner** — Analyzes user intent (query type, domain, temporal scope, expertise level) and decomposes the query into 3-7 sub-questions with memory context from past research
5. **WebAgents** (parallel) — Autonomous ReAct agents that search, read, follow links, and extract content. Each has access to `web_search`, `search_news`, `quick_answer`, `fetch_url`, `crawl_links`, and optionally `academic_search`
6. **Synthesizer** — Merges all findings into a structured report with evidence chains, confidence levels, and a contradictions section
7. **Distiller** *(skipped for simple queries)* — Compresses synthesis into an executive summary with actionable recommendations
8. **Fact-Checker** — Verifies every citation URL in the report (async HEAD requests), flags dead links and unsupported claims
9. **Critic** — Rigorously reviews for completeness, hallucination, recency, and contradictions. Triggers re-planning if gaps are found (up to 3 iterations)
10. **Memory storage** — Stores the distilled summary in Turso (rolling buffer) and Qdrant (semantic search) for future context

All orchestration happens through a custom **async DAG pipeline** built on Python's `graphlib.TopologicalSorter`. Independent nodes run concurrently, dependent nodes wait automatically. No external workflow engine.

## What I Learned About AgentScope

Building this project covered several core AgentScope concepts — and then went beyond them:

- **AgentBase and ReActAgent** — Subclassing agents, implementing `reply()`, using the ReAct loop with tool calling
- **Toolkit and tool registration** — Registering async Python functions as tools agents can invoke via `register_tool_function()`
- **Msg and metadata** — Passing both human-readable content and structured data via `Msg.metadata`
- **Formatters** — Using `OpenAIChatFormatter` to convert `Msg` objects into the dict format the model expects
- **Model abstraction** — Configuring LLMs through AgentScope's model layer (with `stream=False` for non-streaming completions)
- **Pipeline patterns** — `SequentialPipeline`, `FanoutPipeline`, and `MsgHub` for multi-agent coordination
- **Where AgentScope stops, you build** — The framework doesn't ship a DAG executor, so we built one. That turned out to be the most valuable part of the project.

**Why AgentScope over LangGraph?** LangGraph is the dominant choice, so picking AgentScope forced a deeper understanding of agent orchestration. AgentScope treats agents as *objects that talk to each other* (actor-model), while LangGraph treats them as *functions that update graph state* (workflow engine). Both are valid; this project intentionally leaned into the actor-model side.

## Key Technical Components

### Mixture-of-Experts Router
A single cheap classification call decides:
- Which models each agent uses (`gpt-4o-mini` for simple, `gpt-4o` for complex synthesis/critique)
- Which agents to skip entirely (validator and distiller are skipped for simple queries)
- How many iterations and sub-questions are allowed

Result: **50-70% token savings on simple queries**, full rigor maintained on complex ones.

### Hybrid Memory
- **Turso (libSQL)** — Sessions, users, share links, templates, rolling memory buffer
- **Qdrant Cloud** — Semantic search over past research using `text-embedding-3-small`
- Before each new query, similar past research is fetched and injected into the planner's context

### Unified WebAgent
Replaces the old separate Searcher + Reader agents with a single autonomous agent that has access to all web tools. It decides what to search, which URLs to read, when to follow links, and when to stop — all in one ReAct loop.

### 5-Strategy Web Scraper
The `fetch_url` tool tries strategies in order until one works:
1. **trafilatura.fetch_url** — handles cookies, redirects, compression, retries
2. **httpx with browser headers** — direct fetch with Chrome user-agent
3. **Alternate user-agent** — Safari UA (some sites treat it differently)
4. **Structured data extraction** — meta tags + JSON-LD (works behind login walls)
5. **Wayback Machine** — archive snapshot as last resort

Plus specialized extractors for:
- **YouTube transcripts** via `youtube-transcript-api` + oEmbed for titles
- **PDFs** via PyMuPDF (remote download + text extraction)
- **GitHub repos/files** via raw content URLs and the GitHub API

### Resilience Features
- **Premise validator** — Catches nonsense queries before wasting tokens on research
- **Citation verification** — Every URL in the report is checked for liveness
- **Credibility scoring** — Sources are tiered (tier1: .edu/.gov/Nature/arXiv; tier2: .org/major news; low: Medium/Reddit)
- **Contradiction detection** — Synthesis prompt enforces explicit "Contradictions & Conflicts" section
- **Recency awareness** — Critic flags reports that rely on outdated sources

## Project Structure

```
.
├── config/
│   └── model_config.json            # Legacy model configs (MoE router is authoritative)
│
├── src/deep_research/
│   ├── agents/                       # validator, planner, web_agent, synthesizer, distiller, critic
│   ├── moe/                          # Query classifier + model router
│   ├── dag/                          # Async DAG engine (engine, nodes, builder)
│   ├── tools/                        # web_search, web_reader, academic_search,
│   │                                 # source_scorer, fact_checker, open_access (Unpaywall)
│   ├── pipeline/                     # Orchestration with MoE + DAG + iteration loop
│   ├── prompts/                      # Markdown system prompts per agent
│   ├── schemas/                      # Pydantic models for structured data exchange
│   ├── db/                           # Turso client, users, sessions, shares, templates, memory
│   ├── vector/                       # Qdrant client, embeddings, research memory
│   ├── auth/                         # JWT + bcrypt authentication
│   ├── api/                          # FastAPI backend with SSE streaming
│   └── main.py                       # Entry point
│
├── frontend/                         # React + Vite 8 + TypeScript (ChatGPT-style chat UI)
│   └── src/
│       ├── components/               # Sidebar, MessageBubble, DAGInline, ArtifactFrame,
│       │                             # ChatInput, ReasoningPanel, WelcomeScreen, AuthModal, ...
│       ├── hooks/                    # useAuth, useResearch, useHistory
│       ├── pages/                    # SharedView (public research links)
│       └── styles/                   # White/blue tonal theme, Emil Kowalski design principles
│
└── tests/                            # test_backend.py + test_moe.py (31 passing tests)
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (or Bun)
- An [OpenAI API key](https://platform.openai.com/api-keys) — required (used for LLMs and embeddings)
- Optional: [Turso](https://turso.tech) account for cloud DB, [Qdrant Cloud](https://cloud.qdrant.io) for vector search

### Install

```bash
# Clone and enter the project
cd Deep-Research

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install Python dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env and add at least OPENAI_API_KEY and JWT_SECRET

# Install frontend dependencies
cd frontend
bun install  # or npm install
cd ..
```

### Run

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — Backend
python -m deep_research.main

# Terminal 2 — Frontend
cd frontend
bun dev  # or npm run dev
```

Open http://localhost:3000 in your browser. Register an account, then start researching.

### Run Tests

```bash
pytest
```

All 31 tests should pass (DAG engine, MoE router, auth, database CRUD, fact-checker, tool functions).

## Usage

1. Register an account on first visit
2. Pick a template (Market Analysis, Literature Review, Tech Comparison, Due Diligence, News Briefing) or type a freeform query
3. Select a depth:
   - **Quick** — 1 iteration, ~3 sources, fastest and cheapest
   - **Standard** — Up to 2 iterations, ~5 sources, good balance
   - **Deep** — Up to 3 iterations, ~7 sources, most thorough (forces complex MoE route)
4. Watch the DAG visualization as WebAgents work in parallel
5. Read the final report with inline citations, evidence chains, and verified sources
6. **Ask follow-up questions** in the same chat — context carries forward via memory
7. **Share** completed research via a public link, or **Export** as a JSON artifact

## Tech Stack

| Layer                | Technology                                                                 |
| -------------------- | -------------------------------------------------------------------------- |
| Agent Framework      | [AgentScope](https://github.com/agentscope-ai/agentscope)                   |
| LLM                  | OpenAI (`gpt-4o-mini` default; `gpt-4o` for complex synthesis/critique)    |
| Embeddings           | OpenAI `text-embedding-3-small`                                            |
| Web Search           | DuckDuckGo (`ddgs`) with optional Tavily fallback                          |
| Content Extraction   | `trafilatura`, `pymupdf` (PDFs), `youtube-transcript-api`, GitHub API       |
| DAG Execution        | Python `graphlib.TopologicalSorter` + `asyncio`                            |
| Database             | [Turso](https://turso.tech) (libSQL) — local SQLite fallback               |
| Vector Search        | [Qdrant Cloud](https://qdrant.tech)                                        |
| Academic Sources     | [Semantic Scholar](https://www.semanticscholar.org/) + [Unpaywall](https://unpaywall.org/) |
| Backend              | FastAPI + SSE streaming                                                    |
| Authentication       | JWT (python-jose) + bcrypt + refresh token rotation                        |
| Frontend             | React 19 + Vite 8 (Oxc bundler) + TypeScript                                |

## Cost Estimate (with MoE routing)

| Depth    | Tokens (est.) | LLM Cost    | Total     |
| -------- | ------------- | ----------- | --------- |
| Quick    | ~12K          | ~$0.03      | ~$0.03    |
| Standard | ~45K          | ~$0.12      | ~$0.12    |
| Deep     | ~95K          | ~$0.35      | ~$0.35    |

Web search is free (DuckDuckGo). MoE routing cuts simple-query costs by ~70% vs a fixed-model pipeline.
