---
type: Component
title: "Agent Middleware Pipeline"
description: "The LangChain agent middlewares: Skill injection, single-round business RAG + lexicon retrieval into the Context API, context-window warning, prompt compiler (system-message merge), and RAG prompt injection."
tags: [architecture, middleware, rag, prompt]
openwiki:
  roles: [architecture]
  change_kinds: [lifecycle]
  source_paths: [backend/app/agent/middleware/__init__.py, backend/app/agent/middleware/skill_middleware.py, backend/app/agent/middleware/rag_middleware.py, backend/app/agent/middleware/prompt_compiler_middleware.py, backend/app/agent/middleware/context_warning_middleware.py, backend/app/agent/middleware/rag_prompt_injector_middleware.py]
  symbols: [SkillMiddleware, BusinessRagMiddleware, PromptCompilerMiddleware, ContextWarningMiddleware, RagPromptInjectorMiddleware, ULTIMATE_DELETION_TOOLS, COLLAPSIBLE_TOOLS]
  test_paths: [backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py, backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py, backend/tests/agent/test_context_api_transient_flow.py]
  invariants:
    - RAG docs and lexicon DDL flow through RequestContext (Context API), never through checkpointed state.
    - PromptCompilerMiddleware merges all system messages into a single leading system message to satisfy strict local engines (vLLM).
  validation_commands: ["cd backend && python -m pytest tests/agent/middleware tests/agent/vector/sql_lexicon/test_rag_middleware.py -q"]
---

# Agent Middleware Pipeline

`backend/app/agent/middleware/` holds the `AgentMiddleware` subclasses that shape every model call. They are assembled in [agent-service](agent-service.md); export list in `backend/app/agent/middleware/__init__.py`.

| Middleware | Owns | Mounted on |
|---|---|---|
| `SkillMiddleware` | Registers `load_skill` / `load_scenario` tools; injects the available-skill catalog + active-domain DDL into the prompt; `before_agent` narrows `skills_loaded` to the active skill | SQL subagent only (see [subagent-sql](subagent-sql.md)) |
| `BusinessRagMiddleware` | Single-round retrieval: `retriever.aretrieve` (+ optional reranker) plus the DB-lexicon `retrieve_all`, then writes `rag_context` / `rag_query` / `lexicon_context` into `runtime.context` (the Context API) and degrades to empty on error | Main agent |
| `RagPromptInjectorMiddleware` | Reads `RequestContext.rag_context` and injects the retrieved RAG text into the system message at the pre-model moment | Main agent |
| `PromptCompilerMiddleware` | Merges the static system prompt + active-skill DDL + RAG + system date into one leading system message; collapses/deletes stale tool-call history (`ULTIMATE_DELETION_TOOLS`, `COLLAPSIBLE_TOOLS`) | SQL subagent |
| `ContextWarningMiddleware` | Estimates input tokens (via the configured token estimator) and emits a `context_warning` payload recommending a new session near the window limit | Main agent |

## How retrieval avoids repeated work

The design is a **single-retrieval, deep-copy inheritance** model (spec in `docs/deepagent/rag_single_retrieval_spec.md`): `BusinessRagMiddleware` runs once at the main-agent entry point, and the `deepagents` subgraph mechanism deep-copies the context so the subagent inherits the same round's RAG/lexicon without re-querying. This is why retrieval is mounted on the main agent while prompt compilation happens in the subagent.

## Prompt compiler details

`PromptCompilerMiddleware` (in `backend/app/agent/middleware/prompt_compiler_middleware.py`) solves the multi-system-message 400 error that strict local engines (e.g. vLLM) raise. It physically drains every `system` message and merges them into index 0 before counting/compiling. The `ULTIMATE_DELETION_TOOLS` set (the three `search_db_*_lexicon` tools) and `COLLAPSIBLE_TOOLS` set control which historical tool calls are physically deleted vs. folded.

## Invariants & tests

- RAG middleware Context-API injection with zero state pollution: `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py` (`test_business_rag_middleware_abefore_model`, `test_business_rag_middleware_exception_handling`) and `backend/tests/agent/test_context_api_transient_flow.py`.
- RAG prompt injector reads from `RequestContext` and no-ops when empty: `backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py` (`test_rag_prompt_injector_injects_rag_text_into_system_message`, `test_rag_prompt_injector_noop_when_no_lexicon_context`).
- Subagent prompt compilation of DDL: `backend/tests/agent/test_agent_component_boundaries.py::test_sql_subagent_skill_middleware_loading_and_prompt_compilation`.

## Change recipe: add a new middleware

1. Subclass `AgentMiddleware` in `backend/app/agent/middleware/`; export from `__init__.py` (`__all__`).
2. Wire into the correct list in `backend/app/agent/service.py::_build_agent_components` — `subagent_middleware_list` (domain/skill) vs `main_middleware_list` (long-conversation, RAG, context warning).
3. If it reads transient per-round data, read from `runtime.context` (`RequestContext`), not state — see [state-and-context](state-and-context.md).
4. Validate with the middleware + RAG tests above.
