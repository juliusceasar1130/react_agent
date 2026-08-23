---
type: Operations
title: "Deployment & Testing"
description: "How to run, deploy, and validate rearch_agent: dev commands, Docker Compose, dual-database env layout, artifact/Lexicon sync config, and the pytest baseline + markers."
tags: [operations, deployment, testing, docker]
openwiki:
  roles: [operations, testing]
  change_kinds: [ops]
  source_paths: [docker-compose.yml, backend/Dockerfile, run_backend.py, backend/pyproject.toml, AGENTS.md, requirements.txt, requirements-dev.txt]
  validation_commands: [cd backend && python -m pytest -q]
---

# Deployment & Testing

## Running locally

| What | Command | Notes |
|---|---|---|
| Backend (dev) | `uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000` | from repo root; `run_backend.py` is the Windows-safe wrapper (sets `WindowsSelectorEventLoopPolicy` and reload off) |
| Frontend (dev) | `cd frontend && npm run dev` | Vite dev server; build check is `npm run build:check` (`vue-tsc && vite build`) |
| LangGraph managed mode | `langgraph dev --allow-blocking` | `langgraph.json` graph `agent` → `backend/app/agent/service.py:build_agent_graph`; `start_langgraph_dev.bat` wraps this |
| Production | `docker-compose up -d --build` | `docker-compose.yml` builds `backend/Dockerfile` (`python:3.12-slim`, `WORKDIR /app`, `PYTHONPATH=/app` so `backend.app.*` absolute imports resolve); joins an **external** network `savedatabase-postgresql_v2_app-network` and mounts `./backend/app/skills/domains` as a volume (skill content ships without image rebuild) |

The frontend assumes an Nginx proxy in production that maps `/rearch/*` → backend; dev relies on `VITE_...`/relative paths — see `frontend/src/api/index.ts`.

## Configuration

All settings are `pydantic-settings`-driven from `.env` (repo root; `.env_docker` is the Compose variant) — canonical source is `backend/app/config.py`. **Never commit real secrets; the wiki documents config surface only.**

Key config groups (env var → meaning):

| Group | Variables | What they control |
|---|---|---|
| LLM | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `OLLAMA_*`, `AGENT_TEMPERATURE`, `AGENT_MAX_TOKENS` | Provider selection ([agent-service](../architecture/agent-service.md)) |
| Prompts | `MAIN_SYSTEM_PROMPT_PATH` (main orchestrator prompt), `SYSTEM_PROMPT_PATH` (SQL subagent prompt) | Paths to the file-backed system prompt templates; defaults resolve to the checked-in `backend/app/agent/prompts/` and `backend/app/agent/subagents/sql/` files ([agent-prompts](../architecture/agent-prompts.md)) |
| Databases | `DATABASE_URL` (chat sessions + agent checkpoints + pgvector `rag_store`), `ANALYTICS_DATABASE_URL` + `ANALYTICS_DB_SEARCH_PATH` (business SQL target) | Two distinct Postgres roles: app DB vs. analytics DB |
| SQL safety | `SQL_AGENT_TOP_K`, `SQL_RESULT_HARD_LIMIT`, `SQL_RESULT_PREVIEW_ROWS`, `DIMENSION_RESULT_HARD_LIMIT`, `DIMENSION_TABLES`, `SQL_LINTER_ENABLED`, `SQL_LINTER_DISABLED_RULES`, `SQL_CHECKER_MODE` | Guard pipeline in [tools-and-sql-linter](../architecture/tools-and-sql-linter.md) |
| RAG / lexicon | `RAG_BACKEND` (`pgvector` \| `milvus_hybrid`), `RAG_SIMILARITY_THRESHOLD`, `MILVUS_*`, `EMBEDDING_PROVIDER`, `RERANK_*`, `NVIDIA_API_KEY`, `DB_LEXICON_SYNC_ON_STARTUP`, `MILVUS_OVERWRITE` | Retrieval in [rag-and-lexicon](../domain/rag-and-lexicon.md); startup lexicon sync task in `backend/app/main.py` |
| Artifacts | `ARTIFACTS_DIR`, `ARTIFACTS_TTL_HOURS` (legacy `CHART_ARTIFACT_DIR`, `SQL_EXPORT_DIR`, `*_TTL_HOURS`) | [artifact-lifecycle](../workflows/artifact-lifecycle.md) |
| Context management | `LLM_CONTEXT_WINDOW`, `LLM_CONTEXT_WARN_TOKENS`, `LLM_CONTEXT_SAFETY_BUFFER`, `LLM_CONTEXT_SUMMARIZE_TRIGGER_TOKENS`, `TOKEN_ESTIMATOR_ENGINE` (`llama_cpp` \| `vllm`) | Context warning + summarization ([middleware-pipeline](../architecture/middleware-pipeline.md)) |
| Call limits | `AGENT_MODEL_CALL_RUN_LIMIT`, `AGENT_TOOL_CALL_RUN_LIMIT`, `AGENT_CALL_LIMIT_EXIT_BEHAVIOR` | Anti-loop circuit breakers |

The OpenWiki wiki itself is refreshed by `.github/workflows/openwiki-update.yml` (scheduled + manual, `openwiki code --update` with LangSmith connector).

## Test suite

Baseline config in `backend/pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = [".."]` (repo root on `sys.path`, so `backend.app.*` imports resolve when running from `backend/`), `addopts = "-m 'not integration'"`, markers `integration` (needs live Milvus/Postgres/LLM) and `smoke` (against a running backend).

| Tier | Command | Scope |
|---|---|---|
| Focused (default, quiet) | `cd backend && python -m pytest <path> -q` | Unit + mock-based tests; `-q` keeps output narrow, failures stay full |
| Whole non-integration suite | `cd backend && python -m pytest -q` | `tests/` tree minus `integration`/`smoke` marked tests |
| **Conditional** integration | `cd backend && python -m pytest -m integration` | Only when live Postgres/Milvus/LLM are available; otherwise tests skip or fail on connection |
| **Conditional** smoke | `cd backend && python -m pytest tests/smoke -m smoke` | Golden-path end-to-end; requires a running backend (`run_backend.py`) |
| Frontend | `cd frontend && npx vue-tsc --noEmit` | Type-level check; there is no frontend unit-test suite |

Test layout (see each page's `test_paths` for the focused sets):

- `backend/tests/agent/` — agent unit tests (state sandboxing, context flow, tool compatibility, middleware, RAG/lexicon, persistence).
- `backend/tests/test_routers_coverage.py` — endpoint-level coverage for all routers including stream/resume.
- `backend/tests/test_tool_artifacts_persistence.py`, `test_scenario_quick_panel_*.py` — persistence + scenario engine.
- `backend/tests/smoke/test_smoke_golden_path.py` — conditional golden path.

## Where the wiki points for deeper ops context

- Design intent: `docs/` (RAG deployment notes in `docs/llamaindex_rag/` and `docs/progresql_vector开发指南/`, architecture reports in `docs/deepagent/`, agent best practices in `docs/agent_best_practices.md`).
- Change log: root `changelog.md` (large; grep by feature name rather than reading whole).
- OpenSpec deltas for architectural changes: `openspec/`.
