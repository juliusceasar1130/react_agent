---
type: 组件
title: "代理服务与组装（SQLAgentService）"
description: "说明主 DeepAgent 及其 SQL 子代理的组装方式：同步/异步双初始化路径、LLM 工厂、token 估算器、调用限制中间件，以及 FastAPI 生命周期包装器。"
tags: [architecture, agent, langgraph, lifecycle]
openwiki:
  roles: [architecture, runtime]
  change_kinds: [lifecycle, tooling]
  source_paths: [backend/app/agent/service.py, backend/app/agent/llm.py, backend/app/services/chat_service.py]
  symbols: [SQLAgentService, build_agent_graph, _build_agent_components, _build_main_system_prompt, create_local_async, ReasoningAwareChatDeepSeek]
  test_paths: [backend/tests/agent/test_persistence_integration.py, backend/tests/agent/test_chat_deepseek_integration.py, backend/tests/agent/test_agent_component_boundaries.py]
  invariants:
    - Sync init path (_initialize_agent) and async init path (_ainitialize_agent) must stay 100% in sync; both call the shared _build_agent_components.
    - Managed (LangGraph) mode never creates local checkpointer resources; local mode reuses injected checkpointer/store if provided.
  validation_commands: [cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py -q]
---

# 代理服务与组装（`SQLAgentService`）

`backend/app/agent/service.py` 负责整个代理系统的组装。公开类是 `SQLAgentService`；LangGraph 运行时的图工厂是 `build_agent_graph`（`langgraph.json` 中唯一的入口点）。

## 符号映射

| 符号 | 文件 | 角色 |
|---|---|---|
| `SQLAgentService` | `backend/app/agent/service.py` | 核心服务；`__init__` 触发同步初始化；`create_local_async()` 是 FastAPI 使用的异步工厂 |
| `_build_agent_components` | `backend/app/agent/service.py` | 组件信息的单一来源：LLM、DB、工具、RAG、提示词、中间件。两条初始化路径都会调用它，从而保持一致 |
| `build_agent_graph` | `backend/app/agent/service.py` | LangGraph 工厂（`managed_runtime=True`），缓存模块级 `_MANAGED_AGENT_SERVICE` 单例，使图构建更轻量 |
| `_create_local_checkpointer` / `_create_local_async_checkpointer` | `backend/app/agent/service.py` | 本地模式持久化：`PostgresSaver`（同步）/ `AsyncPostgresSaver` + 基于 `DATABASE_URL` 的 `psycopg_pool` |
| `_build_main_system_prompt` / `_main_prompt_loader` | `backend/app/agent/service.py` | 通过共享 `SystemPromptLoader`，基于 `MAIN_SYSTEM_PROMPT_PATH` 模板将主代理的系统提示词构建为普通字符串（详见 [agent-prompts](agent-prompts.md)） |
| `_create_llm` | `backend/app/agent/llm.py` | 模型工厂：默认使用 `ReasoningAwareChatDeepSeek`（别名 `QwenChatDeepSeek`），在 `use_ollama` 时使用 `ChatOllama`；将 vLLM 的 `reasoning`/`reasoning_content` 字段映射到 `additional_kwargs["reasoning_content"]` |
| `LlamaCppTokenEstimator` / `VllmTokenEstimator` | `backend/app/agent/utils/*_token_estimator.py` | 用于上下文警告/摘要的 token 估算；估算引擎由 `settings.token_estimator_engine` 选择 |
| `SQLAgentService` (wrapper) | `backend/app/services/chat_service.py` | FastAPI 兼容层：`process_stream`、`process_message`、`process_stream_resume`；此外，`initialize_agent_service` / `get_agent_service` / `shutdown_agent_service` 单例已接入 `backend/app/main.py` 中的应用生命周期 |

## 初始化流程

1. `_build_agent_components()` 以无状态方式构建所有内容：
   - 通过 `_create_llm`（`backend/app/agent/llm.py`）创建 LLM；通过 `MaterializedViewSQLDatabase` 连接 `ANALYTICS_DATABASE_URL`（业务数据）；通过 `create_business_retriever_and_reranker` 创建 RAG（参见 [rag-and-lexicon](../domain/rag-and-lexicon.md)）。
   - 通过 `_prepare_tools` 构建工具：封装的 `sql_db_query`、可选的 SQL 示例搜索、`build_chart_artifact`、`export_to_csv`、`AskUserQuestion`，以及三个数据库词典工具（参见 [tools-and-sql-linter](tools-and-sql-linter.md)）。
   - 子代理：使用 `state_schema=SqlSubAgentState`、`context_schema=RequestContext` 调用 `create_agent(...)`，并封装为 `CompiledSubAgent(name="sql_domain_agent")`（参见 [subagent-sql](subagent-sql.md)）。
   - 主代理：使用子代理、主工具 `[AskUserQuestion()]`、由 `_build_main_system_prompt()` 生成的基于文件的主系统提示词（[agent-prompts](agent-prompts.md)）、`SummarizationMiddleware`（其 `exact_token_counter` 在计数前将所有系统消息物理合并到位置 0）、`ContextWarningMiddleware`、`RagPromptInjectorMiddleware`，以及调用限制中间件（`ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` 分别由 `settings.agent_model_call_run_limit` / `agent_tool_call_run_limit` 配置）。
2. 持久化：本地模式创建检查点器；托管模式跳过（由 LangGraph 注入）。
3. `_create_agent_from_components` 完成图构建。关闭时，`aclose()` 释放本地异步连接池。

## 不变量

- **双路径一致性**：`_initialize_agent`（同步）和 `_ainitialize_agent`（异步）都必须调用 `_build_agent_components` 并保持行为一致——这一点在 `AGENTS.md` 中被明确说明。
- **中间件归属边界**：主代理不携带 `SkillMiddleware`，也不携带领域工具；SQL 子代理独占 `SkillMiddleware` + `PromptCompilerMiddleware`。由 `backend/tests/agent/test_agent_component_boundaries.py::test_main_agent_and_subagent_middleware_and_tools_boundaries` 强制执行。
- **RAG doc_k**：当存在重排器时 `doc_k=10`，否则为 `5`（在 `_build_agent_components` 中设置）。

## 变更指南：为代理添加中间件或工具

1. 在所属包中实现（`backend/app/agent/middleware/` 或 `backend/app/agent/tools/` / `subagents/sql/tools.py`）。
2. 接入 `_build_agent_components`——选择正确的列表：`subagent_middleware_list` 或 `main_middleware_list`（参见 [middleware-pipeline](middleware-pipeline.md)）。在 `_prepare_tools` 中注册的工具工厂会传入子代理；仅限主代理的工具会被追加到 `main_tools`。
3. 如果组件依赖 RAG 或数据库，请遵循现有的 try/except 降级模式（记录日志并继续），而不是使代理启动直接失败。
4. 验证：`cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py tests/agent/test_tools_main_and_subagent_compatibility.py -q`。

## 变更指南：切换或扩展 LLM 提供商

- 工厂位于 `backend/app/agent/llm.py::_create_llm`；针对 vLLM 的提供商特定采样参数会封装在 `extra_body` 中（`top_k`、`repetition_penalty`）。
- 推理（思考）内容映射位于 `ReasoningAwareChatDeepSeek`；测试：`backend/tests/agent/test_chat_deepseek_integration.py`。
- token 估算器切换（`llama_cpp` 或 `vllm`）仅通过配置完成：`TOKEN_ESTIMATOR_ENGINE`（参见 [deployment-and-testing](../operations/deployment-and-testing.md)）。