---
type: Component
title: "Agent State & Transient Context (State/Context Sandboxing)"
description: "The two-level agent state model: slim global CustomState for the main agent, sandboxed SqlSubAgentState for the SQL subagent, and the Context API (RequestContext) that carries per-round RAG/lexicon payloads with zero checkpoint bloat."
tags: [architecture, state, langgraph, context-api]
openwiki:
  roles: [architecture, domain]
  change_kinds: [state, lifecycle]
  source_paths: [backend/app/agent/state.py, backend/app/agent/context.py]
  symbols: [CustomState, SqlSubAgentState, RequestContext]
  test_paths: [backend/tests/agent/test_state_sandboxing_concurrency.py, backend/tests/agent/test_context_api_transient_flow.py, backend/tests/agent/test_custom_state_concurrent.py]
  invariants:
    - CustomState keeps only messages plus lightweight control flags (context_warning, tool_artifact); skill/scenario fields live exclusively in SqlSubAgentState.
    - RequestContext (Context API) is never checkpointed: 0-byte state growth per round.
    - Concurrent subagents must never write sandbox fields into the parent graph state.
  validation_commands: ["cd backend && python -m pytest tests/agent/test_state_sandboxing_concurrency.py tests/agent/test_context_api_transient_flow.py -q"]
---

# Agent State & Transient Context

`backend/app/agent/state.py` and `backend/app/agent/context.py` define the state model behind the multi-agent design. Design intent (Phase 1 spec) is in `openspec/changes/phase1-state-governance-and-subgraph-isolation/spec.md` and `docs/deepagent/`.

## Symbols

| Symbol | File | Role |
|---|---|---|
| `CustomState` | `backend/app/agent/state.py` | Global persistent state of the main agent: base `messages` plus `context_warning` and `tool_artifact`, each with a `_last_wins` reducer. Checkpoint snapshot stays under ~5 KB |
| `SqlSubAgentState` | `backend/app/agent/state.py` | Subagent-local sandbox: `skills_loaded`, `scenarios_loaded`, `active_skill`, `active_scenario` (all `NotRequired`, `_last_wins`) |
| `RequestContext` | `backend/app/agent/context.py` | LangGraph `context_schema` typed-dict: `lexicon_context`, `rag_context`, `rag_query`, `user_id`, `session_id`. Carried per round via the Context API, transparent to all middlewares and tools |

## Why it exists

- Before Phase 1, domain retrieval data (RAG docs, DDL) and skill bookkeeping lived in checkpointed state, inflating Postgres checkpoints ~10x and causing `INVALID_CONCURRENT_GRAPH_UPDATE` when two subagents ran concurrently.
- Now: transient per-round payloads ride `RequestContext` (never checkpointed), skill bookkeeping is sandboxed per subagent, and subagents communicate back to the parent only via `messages`.

## Invariants & tests

| Invariant | Test |
|---|---|
| `SqlSubAgentState` carries domain fields; `CustomState` is clean | `test_sql_subagent_state_schema_properties` |
| Two concurrent subagents writing different sandbox skills produce zero collisions on the parent graph | `test_concurrent_subagents_sandboxed_zero_collision` |
| Real `asyncio.gather` fan-out of subagents works | `test_real_async_concurrent_subagents_gather` |
| Parent-level concurrent graph update is safe | `backend/tests/agent/test_custom_state_concurrent.py::test_custom_state_concurrent_graph_update` |
| RAG middleware injects into `RequestContext` without polluting state/checkpoint | `test_business_rag_middleware_context_api_injection_and_zero_state_pollution`, `test_checkpoint_zero_pollution_with_context_api` (both in `test_context_api_transient_flow.py`) |
| `RagPromptInjectorMiddleware` and `PromptCompilerMiddleware` read from `RequestContext` | `test_rag_prompt_injector_reads_from_request_context`, `test_prompt_compiler_reads_from_request_context` |

## Change guidance

- **Add a transient per-round payload**: add a key to `RequestContext` in `backend/app/agent/context.py`; populate it in the owning middleware's `abefore_model` (see [middleware-pipeline](middleware-pipeline.md)); read it in tools via `runtime.context` (`ToolRuntime[RequestContext, SqlSubAgentState]` — the native-signature convention fixed in commit 48d5da7).
- **Add a persistent main-agent control flag**: add it to `CustomState` with `NotRequired[Annotated[dict, _last_wins]]`. Keep it small — large payloads belong in the Context API or [artifact side channel](../workflows/artifact-lifecycle.md).
- **Validate**: run the state sandboxing + context flow tests above (both are pure, no live infra).
