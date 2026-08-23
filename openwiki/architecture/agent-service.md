---
type: Component
title: "Agent Service & Assembly (SQLAgentService)"
description: "How the main DeepAgent and its SQL subagent are assembled: dual sync/async init paths, LLM factory, token estimators, call-limit middlewares, and the FastAPI lifecycle wrapper."
tags: [architecture, agent, langgraph, lifecycle]
openwiki:
  roles: [architecture, runtime]
  change_kinds: [lifecycle, tooling]
  source_paths: [backend/app/agent/service.py, backend/app/agent/llm.py, backend/app/services/chat_service.py]
  symbols: [SQLAgentService, build_agent_graph, _build_agent_components, create_local_async, ReasoningAwareChatDeepSeek]
  test_paths: [backend/tests/agent/test_persistence_integration.py, backend/tests/agent/test_chat_deepseek_integration.py, backend/tests/agent/test_agent_component_boundaries.py]
  invariants:
    - Sync init path (_initialize_agent) and async init path (_ainitialize_agent) must stay 100% in sync; both call the shared _build_agent_components.
    - Managed (LangGraph) mode never creates local checkpointer resources; local mode reuses injected checkpointer/store if provided.
  validation_commands: [cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py -q]
---

# Agent Service & Assembly (`SQLAgentService`)

`backend/app/agent/service.py` owns the assembly of the entire agent system. The public class is `SQLAgentService`; the graph factory for the LangGraph runtime is `build_agent_graph` (the only entry point in `langgraph.json`).

## Symbol map

| Symbol | File | Role |
|---|---|---|
| `SQLAgentService` | `backend/app/agent/service.py` | Core service; `__init__` triggers sync init; `create_local_async()` is the async factory used by FastAPI |
| `_build_agent_components` | `backend/app/agent/service.py` | Single source of component truth: LLM, DB, tools, RAG, prompts, middlewares. Both init paths call it, keeping them in sync |
| `build_agent_graph` | `backend/app/agent/service.py` | LangGraph factory (`managed_runtime=True`), caches a module-level `_MANAGED_AGENT_SERVICE` singleton so graph builds are cheap |
| `_create_local_checkpointer` / `_create_local_async_checkpointer` | `backend/app/agent/service.py` | Local-mode persistence: `PostgresSaver` (sync) / `AsyncPostgresSaver` + `psycopg_pool` over `DATABASE_URL` |
| `_create_llm` | `backend/app/agent/llm.py` | Model factory: `ReasoningAwareChatDeepSeek` (alias `QwenChatDeepSeek`) by default, `ChatOllama` when `use_ollama`; maps vLLM `reasoning`/`reasoning_content` fields into `additional_kwargs["reasoning_content"]` |
| `LlamaCppTokenEstimator` / `VllmTokenEstimator` | `backend/app/agent/utils/*_token_estimator.py` | Token estimation for context warning/summarization; engine chosen by `settings.token_estimator_engine` |
| `SQLAgentService` (wrapper) | `backend/app/services/chat_service.py` | FastAPI compatibility layer: `process_stream`, `process_message`, `process_stream_resume`; plus `initialize_agent_service` / `get_agent_service` / `shutdown_agent_service` singletons wired into the app lifespan in `backend/app/main.py` |

## Init flow

1. `_build_agent_components()` builds everything state-free:
   - LLM via `_create_llm` (`backend/app/agent/llm.py`), DB via `MaterializedViewSQLDatabase` against `ANALYTICS_DATABASE_URL` (business data), RAG via `create_business_retriever_and_reranker` (see [rag-and-lexicon](../domain/rag-and-lexicon.md)).
   - Tools via `_prepare_tools`: wrapped `sql_db_query`, optional SQL-example search, `build_chart_artifact`, `export_to_csv`, `AskUserQuestion`, and the three DB-lexicon tools (see [tools-and-sql-linter](tools-and-sql-linter.md)).
   - Subagent: `create_agent(...)` with `state_schema=SqlSubAgentState`, `context_schema=RequestContext`, wrapped into `CompiledSubAgent(name="sql_domain_agent")` (see [subagent-sql](subagent-sql.md)).
   - Main agent: `create_deep_agent` with subagents, main tools `[AskUserQuestion()]`, `SummarizationMiddleware` (with an `exact_token_counter` that physically merges all system messages to position 0 before counting), `ContextWarningMiddleware`, `RagPromptInjectorMiddleware`, and call-limit middlewares (`ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` from `settings.agent_model_call_run_limit` / `agent_tool_call_run_limit`).
2. Persistence: local mode creates the checkpointer; managed mode skips it (LangGraph injects).
3. `_create_agent_from_components` completes the graph. `aclose()` releases the local async connection pool on shutdown.

## Invariants

- **Dual-path parity**: `_initialize_agent` (sync) and `_ainitialize_agent` (async) must both call `_build_agent_components` and stay behaviorally identical — this is called out in `AGENTS.md`.
- **Middleware ownership boundary**: the main agent carries no `SkillMiddleware` and no domain tools; the SQL subagent exclusively owns `SkillMiddleware` + `PromptCompilerMiddleware`. Enforced by `backend/tests/agent/test_agent_component_boundaries.py::test_main_agent_and_subagent_middleware_and_tools_boundaries`.
- **RAG doc_k**: when a reranker is present `doc_k=10`, otherwise `5` (set in `_build_agent_components`).

## Change recipe: add middleware or a tool to the agent

1. Implement in the owning package (`backend/app/agent/middleware/` or `backend/app/agent/tools/` / `subagents/sql/tools.py`).
2. Wire into `_build_agent_components` — pick the correct list: `subagent_middleware_list` vs `main_middleware_list` (see [middleware-pipeline](middleware-pipeline.md)). Tool factories registered in `_prepare_tools` flow into the subagent; main-agent-only tools are appended to `main_tools`.
3. If the component depends on RAG or DB, follow the existing try/except degrade pattern (log + continue) rather than hard-failing agent startup.
4. Validate: `cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py tests/agent/test_tools_main_and_subagent_compatibility.py -q`.

## Change recipe: switch or extend the LLM provider

- Factory is `backend/app/agent/llm.py::_create_llm`; provider-specific sampling knobs are wrapped in `extra_body` for vLLM (`top_k`, `repetition_penalty`).
- Reasoning (thinking) content mapping lives in `ReasoningAwareChatDeepSeek`; tests: `backend/tests/agent/test_chat_deepseek_integration.py`.
- Token estimator swap (`llama_cpp` vs `vllm`) is config-only: `TOKEN_ESTIMATOR_ENGINE` (see [deployment-and-testing](../operations/deployment-and-testing.md)).
