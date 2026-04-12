# Deep Research

A multi-agent deep research service built with [AgentScope](https://github.com/agentscope-ai/agentscope). Submit a query, and a team of AI agents collaborates through an async DAG pipeline to produce a comprehensive, sourced research report.

This project was built as a hands-on way to learn AgentScope and understand how its agent abstractions, tool registration, message passing, and pipeline orchestration work in practice. Rather than running through tutorials, the goal was to build something real that exercises the framework's core concepts — agents, tools, memory, and multi-agent coordination.

## How It Works

```
                        +--- Searcher_1 --> Reader_1 ---+
User Query -> Planner --+--- Searcher_2 --> Reader_2 ---+--> Synthesizer --> Critic --> Report
                        +--- Searcher_N --> Reader_N ---+        ^                       |
                                                                 +-- if gaps, re-plan ---+
```

1. **Planner** decomposes your query into 3-7 focused sub-questions
2. **Searchers** run web searches in parallel (one per sub-question) via Tavily
3. **Readers** fetch and extract content from discovered URLs using trafilatura
4. **Synthesizer** merges all findings into a structured markdown report with citations
5. **Critic** reviews the report for completeness and identifies gaps
6. If gaps are found, the pipeline loops back with refined sub-questions (up to 3 iterations)

All of this is orchestrated by a custom **async DAG pipeline** built on Python's `graphlib.TopologicalSorter`. Independent nodes (e.g., all searchers) run concurrently, while dependent nodes (e.g., a reader waiting for its searcher) execute in the correct order automatically.

## What I Learned About AgentScope

Building this project covered several core AgentScope concepts:

- **AgentBase and ReActAgent** — How to subclass agents, implement `reply()`, and use the ReAct loop with tool calling
- **Toolkit and tool registration** — Registering async Python functions as tools that agents can invoke via `register_tool_function()`
- **Msg and metadata** — Using AgentScope's message objects to pass both human-readable content and structured data (via `metadata`) between agents
- **Model abstraction** — Configuring different LLM providers (OpenAI in this case) through AgentScope's model layer
- **Pipeline patterns** — Understanding SequentialPipeline and FanoutPipeline, then building a custom DAG executor on top for more complex workflows

The DAG engine was built from scratch because AgentScope's built-in pipelines (sequential and fanout) didn't cover the topology needed here — where searcher-reader pairs run in parallel but the synthesizer must wait for all readers to finish. This turned out to be a good exercise in understanding *why* frameworks provide the abstractions they do.

## Project Structure

```
.
├── config/
│   └── model_config.json            # LLM model configs per agent role
│
├── src/deep_research/
│   ├── agents/                       # 5 agents: planner, searcher, reader, synthesizer, critic
│   ├── dag/                          # Async DAG engine (engine, nodes, builder)
│   ├── tools/                        # Tavily search + trafilatura web reader
│   ├── pipeline/                     # Research orchestration with DAG + iteration loop
│   ├── prompts/                      # System prompt templates for each agent
│   ├── schemas/                      # Pydantic models for structured data exchange
│   ├── api/                          # FastAPI backend with SSE streaming
│   └── main.py                       # Entry point
│
├── frontend/                         # React + Vite + TypeScript
│   └── src/
│       ├── components/
│       │   ├── QueryInput.tsx        # Research query form + depth selector
│       │   ├── DAGView.tsx           # Live DAG visualization with node status
│       │   └── ReportView.tsx        # Markdown report renderer
│       └── hooks/
│           └── useResearch.ts        # SSE connection + state management
│
└── tests/                            # DAG engine, tools, agents, pipeline tests
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Tavily API key](https://tavily.com/) (free tier available)

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
# Edit .env and add your OPENAI_API_KEY and TAVILY_API_KEY

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Run

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — Backend
python -m deep_research.main

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser.

### Run Tests

```bash
pytest
```

## Usage

1. Type a research query (e.g., "What are the latest advances in quantum computing?")
2. Select a depth:
   - **Quick** — 1 iteration, ~5 sources, fastest
   - **Standard** — Up to 2 iterations, ~12 sources, good balance
   - **Deep** — Up to 3 iterations, ~20 sources, most thorough
3. Click **Research** and watch the DAG visualization as agents work in parallel
4. Read the final report with inline citations

## Tech Stack

| Layer              | Technology                                                          |
| ------------------ | ------------------------------------------------------------------- |
| Agent Framework    | [AgentScope](https://github.com/agentscope-ai/agentscope)              |
| LLM                | OpenAI (gpt-4o-mini for search/read, gpt-4o for synthesis/critique) |
| Web Search         | [Tavily](https://tavily.com/)                                          |
| Content Extraction | [trafilatura](https://github.com/adbar/trafilatura)                    |
| DAG Execution      | Python `graphlib.TopologicalSorter` + `asyncio`                 |
| Backend            | FastAPI + SSE                                                       |
| Frontend           | React + Vite + TypeScript                                           |

## Cost Estimate

| Depth    | LLM Cost         | Search Cost | Total |
| -------- | ---------------- | ----------- | ----- |
| Quick    | ~$0.05 | ~$0.025 | ~$0.08      |       |
| Standard | ~$0.15 | ~$0.06  | ~$0.21      |       |
| Deep     | ~$0.35 | ~$0.10  | ~$0.45      |       |
