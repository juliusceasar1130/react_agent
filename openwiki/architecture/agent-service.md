---
type: 组件
title: "代理服务与组装（SQLAgentService）"
description: "说明主 DeepAgent 及其 SQL 子代理的组装方式：同步/异步双初始化路径、LLM 工厂、token 估算器（首次 tokenize 失败后熔断为保守估算）、调用限制中间件，以及 FastAPI 生命周期包装器。"
tags: [architecture, agent, langgraph, lifecycle]
openwiki:
  roles: [architecture, runtime]
  change_kinds: [lifecycle, tooling]
  source_paths: [backend/app/agent/service.py, backend/app/agent/llm.py, backend/app/services/chat_service.py, backend/app/agent/utils/llama_cpp_token_estimator.py, backend/app/agent/utils/vllm_token_estimator.py, backend/app/config.py, backend/app/main.py]
  symbols: [SQLAgentService, build_agent_graph, _build_agent_components, _build_main_system_prompt, _create_token_estimator, LlamaCppTokenEstimator, VllmTokenEstimator, ContextWarningMiddleware, create_local_async, ReasoningAwareChatDeepSeek]
  test_paths: [backend/tests/agent/test_persistence_integration.py, backend/tests/agent/test_chat_deepseek_integration.py, backend/tests/agent/test_agent_component_boundaries.py, backend/tests/agent/test_tool_error_contract.py]
  invariants:
    - Sync init path (_initialize_agent) and async init path (_ainitialize_agent) must stay 100% in sync; both call the shared _build_agent_components.
    - Managed (LangGraph) mode never creates local checkpointer resources; local mode reuses injected checkpointer/store if provided.
    - LlamaCpp/VllmTokenEstimator circuit-breaks after the first /tokenize HTTP error: one INFO log, _unavailable flag set, all later counts use the conservative fallback with zero additional HTTP round trips.
  validation_commands: [cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py tests/agent/test_tool_error_contract.py -q]
verified:
  - by: openwiki/0.4.3
    at: 2026-08-30T09:34:27.074Z
sources:
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-8147e60d7430e04f096bea17
    resource: repo://backend/app/agent/llm.py
  - id: openwiki-source-41df455c4602803dfcd4a21e
    resource: repo://backend/app/agent/middleware/context_warning_middleware.py
  - id: openwiki-source-be1d78a2f8abe4d10dd814ee
    resource: repo://backend/app/agent/service.py
  - id: openwiki-source-7fef2980ecaa695d2f8d3f90
    resource: repo://backend/app/agent/utils/llama_cpp_token_estimator.py
  - id: openwiki-source-979a5da7c8dfc9bf4d7b96f5
    resource: repo://backend/app/agent/utils/vllm_token_estimator.py
  - id: openwiki-source-4188bfee2e15d969d3152477
    resource: repo://backend/app/config.py
  - id: openwiki-source-55002f5b1d39cf35fd6d60e2
    resource: repo://backend/app/main.py
  - id: openwiki-source-c911225d7d1a23acacd3fa32
    resource: repo://backend/app/services/chat_service.py
  - id: openwiki-source-a141359cfef1f56e998406e5
    resource: repo://backend/tests/agent/test_agent_component_boundaries.py
  - id: openwiki-source-41863953653ad4cd47aa60a2
    resource: repo://backend/tests/agent/test_tool_error_contract.py
  - id: openwiki-source-98e429bbd2f92bd04b4796ee
    resource: repo://changelog.md
  - id: openwiki-source-5bbba7b2a8ea8360ff233d63
    resource: repo://langgraph.json
generated: { by: "openwiki/0.4.3", at: "2026-08-30T09:34:27.074Z" }
---

# 代理服务与组装（`SQLAgentService`）

`backend/app/agent/service.py` 负责整个代理系统的组装。公开类是 `SQLAgentService`；LangGraph 运行时的图工厂是 `build_agent_graph`（`langgraph.json` 中唯一的入口点）。

## 符号映射

| 符号 | 文件 | 角色 |
|---|---|---|
| `SQLAgentService` | `backend/app/agent/service.py` | 核心服务；`__init__` 触发同步初始化；`create_local_async()` 是 FastAPI 使用的异步工厂 |
| `_build_agent_components` | `backend/app/agent/service.py` | 组件信息的单一来源：LLM、DB、工具、RAG、提示词、token 估算器、中间件。两条初始化路径都会调用它，从而保持一致 |
| `build_agent_graph` | `backend/app/agent/service.py` | LangGraph 工厂（`managed_runtime=True`），缓存模块级 `_MANAGED_AGENT_SERVICE` 单例，使图构建更轻量 |
| `_create_local_checkpointer` / `_create_local_async_checkpointer` | `backend/app/agent/service.py` | 本地模式持久化：`PostgresSaver`（同步）/ `AsyncPostgresSaver` + 基于 `DATABASE_URL` 的 `psycopg_pool` |
| `_build_main_system_prompt` / `_main_prompt_loader` | `backend/app/agent/service.py` | 通过共享 `SystemPromptLoader`，基于 `MAIN_SYSTEM_PROMPT_PATH` 模板将主代理的系统提示词构建为普通字符串（详见 [agent-prompts](agent-prompts.md)） |
| `_create_llm` | `backend/app/agent/llm.py` | 模型工厂：默认使用 `ReasoningAwareChatDeepSeek`（别名 `QwenChatDeepSeek`），在 `use_ollama` 时使用 `ChatOllama`；将 vLLM 的 `reasoning`/`reasoning_content` 字段映射到 `additional_kwargs["reasoning_content"]`。采样参数按三段传输分层组装：标准参数（temperature/top_p/presence_penalty）走顶层，vLLM 非标准参数（top_k/min_p/repetition_penalty）走 `extra_body`，`enable_thinking` 走 `extra_body.chat_template_kwargs`——请求期的 profile 覆写遵循同一分层（见 [sampling-profiles](sampling-profiles.md)） |
| `_create_token_estimator` | `backend/app/agent/service.py` | token 估算器工厂：依据 `settings.token_estimator_engine`（`TOKEN_ESTIMATOR_ENGINE`）选择 `VllmTokenEstimator` 或 `LlamaCppTokenEstimator`，vllm 分支在未单独配置时回退到 `deepseek_base_url` / `deepseek_model` |
| `LlamaCppTokenEstimator` / `VllmTokenEstimator` | `backend/app/agent/utils/*_token_estimator.py` | 通过 `/tokenize` 端点统计 token；首次 HTTP 失败后熔断为保守估算（详见下文 [Token 估算器与熔断契约](#token-估算器与熔断契约)） |
| `ContextWarningMiddleware` | `backend/app/agent/middleware/context_warning_middleware.py` | 主代理中间件：用配置的估算器在每次 ModelRequest 上估算输入 token，接近阈值时发出 `context_warning` 载荷与流式状态事件 |
| `SQLAgentService` (wrapper) | `backend/app/services/chat_service.py` | FastAPI 兼容层：`process_stream`、`process_message`、`process_stream_resume`；此外，`initialize_agent_service` / `get_agent_service` / `shutdown_agent_service` 单例已接入 `backend/app/main.py` 中的应用生命周期 |

## 初始化流程

1. `_build_agent_components()` 以无状态方式构建所有内容：
   - 通过 `_create_llm`（`backend/app/agent/llm.py`）创建 LLM；通过 `MaterializedViewSQLDatabase` 连接 `ANALYTICS_DATABASE_URL`（业务数据）；通过 `create_business_retriever_and_reranker` 创建 RAG（参见 [rag-and-lexicon](../domain/rag-and-lexicon.md)）。
   - 通过 `_prepare_tools` 构建工具：封装的 `sql_db_query`、可选的 SQL 示例搜索、`build_chart_artifact`、`export_to_csv`、`AskUserQuestion`，以及三个数据库词典工具（参见 [tools-and-sql-linter](tools-and-sql-linter.md)）。
   - 通过 `_create_token_estimator()` 创建 token 估算器实例，同时供 `ContextWarningMiddleware` 与 `SummarizationMiddleware` 的 `exact_token_counter` 使用（见下文 [Token 估算器与熔断契约](#token-估算器与熔断契约)）。
   - 子代理：使用 `state_schema=SqlSubAgentState`、`context_schema=RequestContext` 调用 `create_agent(...)`，并封装为 `CompiledSubAgent(name="sql_domain_agent")`（参见 [subagent-sql](subagent-sql.md)）。
   - 主代理：使用子代理、主工具 `[AskUserQuestion()]`、由 `_build_main_system_prompt()` 生成的基于文件的主系统提示词（[agent-prompts](agent-prompts.md)）、`SummarizationMiddleware`（其 `exact_token_counter` 在计数前将所有系统消息物理合并到位置 0）、`ContextWarningMiddleware`、`RagPromptInjectorMiddleware`，以及调用限制中间件（`ModelCallLimitMiddleware` / `ToolCallLimitMiddleware` 分别由 `settings.agent_model_call_run_limit` / `agent_tool_call_run_limit` 配置）。
2. 持久化：本地模式创建检查点器；托管模式跳过（由 LangGraph 注入）。
3. `_create_agent_from_components` 完成图构建。关闭时，`aclose()` 释放本地异步连接池。

两条初始化路径（`_initialize_agent` 与 `_ainitialize_agent`）还调用 `_load_profiles()`（`backend/app/agent/config/profile_loader.py`）做采样参数配置的 eager load + fail-fast 校验——YAML 缺失、profile 不全或未知段会在启动时直接抛错（见 [sampling-profiles](sampling-profiles.md)）。

## Token 估算器与熔断契约

上下文警告/摘要依赖对输入 token 的估算。估算器实例在 `_build_agent_components` 中创建一次（`_create_token_estimator`），其**唯一选择旋钮**是 `TOKEN_ESTIMATOR_ENGINE`（`llama_cpp` 默认 | `vllm`，对应 `backend/app/config.py` 的 `settings.token_estimator_engine`），切换引擎不改代码、只改配置并重启（见 [deployment-and-testing](../operations/deployment-and-testing.md)）。

### 两种引擎

- `VllmTokenEstimator`（`backend/app/agent/utils/vllm_token_estimator.py`）：向 vLLM 的 `/tokenize` 端点 POST `{"model": ..., "prompt": ...}` 或 `{"messages": ...}`，读取响应的 `count` 字段。
- `LlamaCppTokenEstimator`（`backend/app/agent/utils/llama_cpp_token_estimator.py`）：向 llama.cpp 的 `/tokenize` 端点 POST `{"content": ..., "add_special": False, "parse_special": True, "with_pieces": False}`，从多种响应结构（`token_count`/`count`/`n_tokens`/`num_tokens`/token 数组等）中提取计数。

### 熔断行为（N5 契约）

- 两个估算器都持有 `_unavailable` 标志。`_tokenize()` 在标志置位时**直接返回 `None`，不再发起任何 HTTP 请求**。
- 首次 `httpx.HTTPError`（典型场景：nInfer 部署没有 `/tokenize` 端点，POST 返回 404）时：仅打一条 INFO 日志（`tokenize 端点不可用（...），已熔断，后续轮次将直接使用保守估算`），随后置位 `_unavailable = True`。
- 熔断后，`count_text_tokens` / `count_messages_tokens` / `count_json_like_tokens` 全部回退到 `_estimate_fallback_tokens`：llama_cpp 为 `max(1, len(text))`，vllm 为 `max(1, len(text) // 2)`。
- **非 HTTP 错误不熔断**：响应非 JSON、结构无法识别仅打 WARNING 并当次兜底，不置位 `_unavailable`。
- 熔断是进程级、持久的：估算器随 agent 服务创建，端点恢复需要重启进程（保守估算只影响上下文阈值判断，属可接受取舍）。这消除了每轮对话多次无效同步 HTTP 往返（同步 `httpx.Client` 阻塞事件循环 + 日志刷屏的隐患）。

### 消费方

- `ContextWarningMiddleware`（`backend/app/agent/middleware/context_warning_middleware.py`）：在 `wrap_model_call` / `awrap_model_call` 中调用 `count_json_like_tokens` 分别估算 `system_message`、`messages`、`tools`，求和后加 `safety_buffer`，达到 `warn_tokens` 时向 `Command` 写入 `context_warning` 载荷并发出流式状态事件。
- `SummarizationMiddleware` 的 `exact_token_counter`（`_build_agent_components` 内闭包）：先把所有 `system` 消息物理抽干合并为一条并强制放到位置 0，再调用估算器——vllm 引擎走 `count_messages_tokens`（messages 载荷），llama_cpp 引擎没有该方法，回退到 `count_json_like_tokens`。

### 回归测试

`backend/tests/agent/test_tool_error_contract.py` 用伪造的每次 POST 都抛 404 的 `_FailingClient` 验证熔断契约：`test_vllm_estimator_breaker_on_http_failure` 与 `test_llama_cpp_estimator_breaker_on_http_failure` 断言首次失败后的多次计数与首次一致，且 `fake.post_count == 1`（熔断后不再发出 tokenize 请求）。

## 不变量

- **双路径一致性**：`_initialize_agent`（同步）和 `_ainitialize_agent`（异步）都必须调用 `_build_agent_components` 并保持行为一致——这一点在 `AGENTS.md` 中被明确说明。
- **中间件归属边界**：主代理不携带 `SkillMiddleware`，也不携带领域工具；SQL 子代理独占 `SkillMiddleware` + `PromptCompilerMiddleware`。由 `backend/tests/agent/test_agent_component_boundaries.py::test_main_agent_and_subagent_middleware_and_tools_boundaries` 强制执行。
- **RAG doc_k**：当存在重排器时 `doc_k=10`，否则为 `5`（在 `_build_agent_components` 中设置）。
- **Token 估算器熔断**：`/tokenize` 首次 HTTP 失败后必须熔断（一条 INFO + `_unavailable` 置位），后续计数零 HTTP 直接走保守估算——由 `backend/tests/agent/test_tool_error_contract.py` 的 `test_vllm_estimator_breaker_on_http_failure`、`test_llama_cpp_estimator_breaker_on_http_failure` 强制执行。改动 token 计数或 LLM 接线时不得引入每请求重复的同步 HTTP 往返。

## 变更指南：为代理添加中间件或工具

1. 在所属包中实现（`backend/app/agent/middleware/` 或 `backend/app/agent/tools/` / `subagents/sql/tools.py`）。
2. 接入 `_build_agent_components`——选择正确的列表：`subagent_middleware_list` 或 `main_middleware_list`（参见 [middleware-pipeline](middleware-pipeline.md)）。在 `_prepare_tools` 中注册的工具工厂会传入子代理；仅限主代理的工具会被追加到 `main_tools`。
3. 如果组件依赖 RAG 或数据库，请遵循现有的 try/except 降级模式（记录日志并继续），而不是使代理启动直接失败。
4. 验证：`cd backend && python -m pytest tests/agent/test_agent_component_boundaries.py tests/agent/test_tools_main_and_subagent_compatibility.py -q`。

## 变更指南：切换或扩展 LLM 提供商

- 工厂位于 `backend/app/agent/llm.py::_create_llm`；针对 vLLM 的提供商特定采样参数会封装在 `extra_body` 中（`top_k`、`repetition_penalty`）。
- 推理（思考）内容映射位于 `ReasoningAwareChatDeepSeek`；测试：`backend/tests/agent/test_chat_deepseek_integration.py`。
- token 估算器切换（`llama_cpp` 或 `vllm`）仅通过配置完成：`TOKEN_ESTIMATOR_ENGINE`（`settings.token_estimator_engine`，唯一选择旋钮），供 `ContextWarningMiddleware` 与摘要计数使用（参见 [deployment-and-testing](../operations/deployment-and-testing.md) 与上文 [Token 估算器与熔断契约](#token-估算器与熔断契约)）。
- 请求期的采样参数覆写（thinking/fast 二档 + `thinking_level` 强度）由中间件从 `configurable` 注入，与 `_create_llm` 的 init-time 默认值形成两层：客户端显式传参才覆写（`None` 时保留启动默认）。传输位置开关 `REASONING_EFFORT_TRANSPORT`（ninfer=top_level / vLLM ≤0.27.1=chat_template_kwargs）见 [sampling-profiles](sampling-profiles.md)。
