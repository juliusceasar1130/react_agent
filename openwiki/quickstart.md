---
type: Quickstart
title: "OpenWiki Quickstart — rearch_agent"
description: "Entry point to the rearch_agent knowledge base: what the system is, how the wiki is organized, and a task-routing table to reach the owning source, symbols, focused tests, and minimal validation for a change."
tags: [quickstart, navigation]
openwiki:
  roles: [repository]
  change_kinds: [navigation]
---

# OpenWiki Quickstart — rearch_agent

**rearch_agent** is a production data-query chat system: a FastAPI + LangGraph **DeepAgent** backend (a main coordinator agent plus a compiled **SQL domain subagent**) answers business questions against a PostgreSQL analytics database, with domain Skills, RAG + a three-layer DB lexicon, structured SSE streaming, human-in-the-loop clarification, and a unified artifact store for charts/CSV/tables. The frontend is a Vue 3 + Pinia SPA.

## How this wiki is organized

- **[Architecture](architecture/overview.md)** — the runtime topology, dual persistence modes, and the agent assembly / state / subagent / middleware / tool subsystems; the file-backed system prompt templates and their main↔subagent collaboration contract live in [agent-prompts](architecture/agent-prompts.md).
- **[Domain](domain/skills-and-scenarios.md)** — skills & scenarios, RAG & lexicon, and the chat data model.
- **[Workflows](workflows/streaming-protocol.md)** — cross-component flows: SSE streaming, the clarification loop, and the artifact side-channel.
- **[Frontend](frontend/chat-app.md)** — the Vue SPA.
- **[Operations](operations/deployment-and-testing.md)** — how to run, deploy, and validate.

Each page lists its owning source paths, key symbols, invariants, focused tests, and a change recipe, so you can navigate from intent to code without a repo-wide search.

## Task routing table

| Change area / intent | Wiki page | Source entry points | Key symbols / types | Focused tests | Minimal validation |
|---|---|---|---|---|---|
| Add a tool / harden a SQL guard | [tools-and-sql-linter](architecture/tools-and-sql-linter.md) | `backend/app/agent/subagents/sql/tools.py`, `backend/app/agent/utils/sql_linter.py` | `create_wrapped_query_tool`, `SQLLinter`, `ToolNames` | `tests/agent/test_tools_main_and_subagent_compatibility.py`, `tests/agent/tools/` | `cd backend && python -m pytest tests/agent/test_tools_main_and_subagent_compatibility.py tests/agent/tools -q` |
| Add a domain skill / scenario | [skills-and-scenarios](domain/skills-and-scenarios.md) | `backend/app/skills/domains/`, `backend/app/routers/scenarios.py` | `reload_skills`, `discover_domains`, `resolve_params` | `tests/test_scenario_quick_panel_api.py` | `cd backend && python -m pytest tests/test_scenario_quick_panel_api.py tests/test_scenario_quick_panel_engine.py -q` |
| Add a middleware / change prompt compilation | [middleware-pipeline](architecture/middleware-pipeline.md) | `backend/app/agent/middleware/`, `backend/app/agent/service.py` | `SkillMiddleware`, `PromptCompilerMiddleware`, `_build_agent_components` | `tests/agent/middleware/`, `tests/agent/vector/sql_lexicon/test_rag_middleware.py` | `cd backend && python -m pytest tests/agent/middleware tests/agent/vector/sql_lexicon/test_rag_middleware.py -q` |
| Edit the system prompts / main↔subagent collaboration contract | [agent-prompts](architecture/agent-prompts.md) | `backend/app/agent/prompts/main_system_prompt.md`, `backend/app/agent/subagents/sql/base_system_prompt.md`, `backend/app/agent/utils/system_prompt_loader.py` | `SystemPromptLoader`, `_build_main_system_prompt`, `_build_system_prompt` | `tests/agent/test_main_system_prompt.py`, `tests/agent/utils/test_system_prompt_loader.py` | `cd backend && python -m pytest tests/agent/test_main_system_prompt.py tests/agent/utils/test_system_prompt_loader.py -q` |
| Switch or extend the LLM / token engine | [agent-service](architecture/agent-service.md) | `backend/app/agent/llm.py`, `backend/app/agent/service.py` | `_create_llm`, `ReasoningAwareChatDeepSeek`, `VllmTokenEstimator` | `tests/agent/test_chat_deepseek_integration.py` | `cd backend && python -m pytest tests/agent/test_chat_deepseek_integration.py -q` |
| Add a stream event type | [streaming-protocol](workflows/streaming-protocol.md) | `backend/app/schemas.py`, `frontend/src/api/chat.ts`, `frontend/src/types/index.ts` | `ChatStreamEvent`, `STREAM_EVENT_TYPES`, `parseStreamEvent` | `tests/test_routers_coverage.py`, `tests/agent/test_subagent_stream_scoping.py` | `cd backend && python -m pytest tests/test_routers_coverage.py -q && cd frontend && npx vue-tsc --noEmit` |
| Add a new artifact kind | [artifact-lifecycle](workflows/artifact-lifecycle.md) | `backend/app/artifacts/`, `backend/app/routers/artifacts.py` | `ArtifactKind`, `ArtifactStore`, `get_artifact_store` | `tests/agent/test_artifact_store_lifecycle.py`, `tests/test_tool_artifacts_persistence.py` | `cd backend && python -m pytest tests/agent/test_artifact_store_lifecycle.py tests/test_tool_artifacts_persistence.py -q` |
| Change state / context sandboxing | [state-and-context](architecture/state-and-context.md) | `backend/app/agent/state.py`, `backend/app/agent/context.py` | `CustomState`, `SqlSubAgentState`, `RequestContext` | `tests/agent/test_state_sandboxing_concurrency.py`, `tests/agent/test_context_api_transient_flow.py` | `cd backend && python -m pytest tests/agent/test_state_sandboxing_concurrency.py tests/agent/test_context_api_transient_flow.py -q` |
| Switch RAG backend / lexicon | [rag-and-lexicon](domain/rag-and-lexicon.md) | `backend/app/agent/vector/factory.py`, `backend/app/agent/vector/sql_lexicon/` | `create_business_retriever_and_reranker`, `DatabaseLexiconRetriever` | `tests/agent/vector/`, `tests/agent/test_retriever_async_contract.py` | `cd backend && python -m pytest tests/agent/vector tests/agent/test_retriever_async_contract.py -q` |
| Add a persisted message field | [data-model-and-persistence](domain/data-model-and-persistence.md) | `backend/app/models.py`, `backend/app/database.py`, `backend/app/schemas.py` | `ChatMessage`, `create_tables` | `tests/test_tool_artifacts_persistence.py` | `cd backend && python -m pytest tests/test_tool_artifacts_persistence.py -q` |
| Clarification / resume behavior | [clarification-flow](workflows/clarification-flow.md) | `backend/app/agent/tools/ask_user_question.py`, `backend/app/routers/chat.py` | `AskUserQuestion`, `QuestionItem`, `stream_message_resume` | `tests/test_routers_coverage.py` | `cd backend && python -m pytest tests/test_routers_coverage.py -q` |
| Frontend message-card / subagent UI | [chat-app](frontend/chat-app.md) | `frontend/src/components/chat/`, `frontend/src/stores/messages.ts` | `useMessagesStore`, `SubagentCard`, `reconstructSubagents` | — (no frontend unit tests) | `cd frontend && npx vue-tsc --noEmit` |
| Run / deploy / configure | [deployment-and-testing](operations/deployment-and-testing.md) | `docker-compose.yml`, `run_backend.py`, `backend/app/config.py` | `Settings`, `langgraph.json` | `tests/smoke/` (conditional) | `cd backend && python -m pytest -q` |

> Validation notes: focused `pytest -q` runs keep output quiet but preserve full failure diagnostics. The `integration` and `smoke` tiers are **conditional** — only run them when live Postgres/Milvus/LLM (or a running backend) are available; see [deployment-and-testing](operations/deployment-and-testing.md).

## Where to start / what to watch out for

- **Two init paths must stay in sync** (`_initialize_agent` vs `_ainitialize_agent`) — change tool/middleware/RAG wiring in `_build_agent_components` so both benefit.
- **Transient data goes through the Context API, not checkpointed state** — put large per-round payloads in `RequestContext`.
- **Side-channel artifacts keep the LLM context lean** — return `Command(update={... tool_artifact})`, not raw rows.
- **New stream events need 3 frontend registrations + the backend union** or they are silently dropped.
- **Offline-only frontend** — no public CDN; localize fonts/libs.

## Backlog

Areas not yet given a dedicated page (source anchor + reason). Promote when the backing source is stable.

- **Root agent-instruction files & repo skill libraries** (`.claude/agents/`, `.agents/skills/`) — developer-facing Claude/agent skill definitions (e.g. `code-explainer`, `code-reviewer`) and `AGENTS.md`/`CLAUDE.md` conventions. Out of scope for the runtime-agent wiki and these files are user-authored (the wiki must not edit `/AGENTS.md`/`CLAUDE.md`); the runtime subagents they *describe* are documented in [subagent-sql](architecture/subagent-sql.md).
- **Docs-only intent reports** (`docs/deepagent/`, `docs/multiagent_sidechannel/`, `docs/llamaindex_rag/`, `docs/superpowers/`) — link-only design intent; the wiki references them from the relevant runtime pages rather than restating them. Revisit as a summary page only if a specific design decision becomes load-bearing.
- **SubAgent Registry / factory pattern** (spec: `docs/superpowers/specs/2026-08-23-multi-agent-prompt-and-architecture-optimization.md`) — planned refactor of `backend/app/agent/subagents/` (registry `__init__.py`, `BaseSubAgentFactory`, per-domain `factory.py`) plus `knowledge_doc_agent` / `iot_device_agent` specialists; **not yet in code** (`subagents/__init__.py` is a comment stub, `service.py` still builds the SQL subagent inline). Documented concisely in [agent-prompts](architecture/agent-prompts.md); promote to a full architecture page when the code lands.
