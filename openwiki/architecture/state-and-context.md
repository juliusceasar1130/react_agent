---
type: 组件
title: "智能体状态与瞬态上下文（状态/上下文沙箱化）"
description: "两级智能体状态模型：为主智能体提供精简的全局 CustomState，为 SQL 子智能体提供沙箱化的 SqlSubAgentState，以及负责携带每轮 RAG/词表负载的 Context API（RequestContext），并保持零检查点膨胀。"
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

# 智能体状态与瞬态上下文

`backend/app/agent/state.py` 和 `backend/app/agent/context.py` 定义了多智能体设计背后的状态模型。设计意图（Phase 1 规范）位于 `openspec/changes/phase1-state-governance-and-subgraph-isolation/spec.md` 和 `docs/deepagent/`。

## 符号

| 符号 | 文件 | 角色 |
|---|---|---|
| `CustomState` | `backend/app/agent/state.py` | 主智能体的全局持久状态：基础 `messages`，外加 `context_warning` 和 `tool_artifact`，每个都带有 `_last_wins` 归约器。检查点快照保持低于 ~5 KB |
| `SqlSubAgentState` | `backend/app/agent/state.py` | 子智能体本地沙箱：`skills_loaded`、`scenarios_loaded`、`active_skill`、`active_scenario`（均为 `NotRequired`、`_last_wins`） |
| `RequestContext` | `backend/app/agent/context.py` | LangGraph `context_schema` 类型字典：`lexicon_context`、`rag_context`、`rag_query`、`user_id`、`session_id`。通过 Context API 按轮次携带，对所有中间件和工具透明 |

## 存在原因

- 在 Phase 1 之前，领域检索数据（RAG 文档、DDL）和技能记录存放在被检查点的状态中，使 Postgres 检查点膨胀约 10 倍，并在两个子智能体并发运行时导致 `INVALID_CONCURRENT_GRAPH_UPDATE`。
- 当前：瞬态的每轮负载承载在 `RequestContext` 上（从不被检查点化），技能记录按子智能体进行沙箱化，并且子智能体仅通过 `messages` 向父级回传。

## 不变量与测试

| 不变量 | 测试 |
|---|---|
| `SqlSubAgentState` 携带领域字段；`CustomState` 保持干净 | `test_sql_subagent_state_schema_properties` |
| 两个并发子智能体写入不同的沙箱技能时，父级图不会产生任何冲突 | `test_concurrent_subagents_sandboxed_zero_collision` |
| 真实的 `asyncio.gather` 子智能体扇出可正常工作 | `test_real_async_concurrent_subagents_gather` |
| 父级并发的图更新是安全的 | `backend/tests/agent/test_custom_state_concurrent.py::test_custom_state_concurrent_graph_update` |
| RAG 中间件向 `RequestContext` 注入数据，且不污染状态/检查点 | `test_business_rag_middleware_context_api_injection_and_zero_state_pollution`、`test_checkpoint_zero_pollution_with_context_api`（两者均位于 `test_context_api_transient_flow.py`） |
| `RagPromptInjectorMiddleware` 和 `PromptCompilerMiddleware` 从 `RequestContext` 读取 | `test_rag_prompt_injector_reads_from_request_context`、`test_prompt_compiler_reads_from_request_context` |

## 变更指导

- **添加瞬态每轮负载**：在 `backend/app/agent/context.py` 的 `RequestContext` 中添加一个键；在所属中间件的 `abefore_model` 中填充它（参见 [middleware-pipeline](middleware-pipeline.md)）；在工具中通过 `runtime.context` 读取它（`ToolRuntime[RequestContext, SqlSubAgentState]` — 在提交 48d5da7 中固定的原生签名约定）。
- **添加持久化主智能体控制标志**：使用 `NotRequired[Annotated[dict, _last_wins]]` 将其添加到 `CustomState`。保持其精简 — 大型负载应放在 Context API 或[制品旁路通道](../workflows/artifact-lifecycle.md)中。
- **验证**：运行上述状态沙箱化和上下文流测试（两者均为纯测试，无需实时基础设施）。