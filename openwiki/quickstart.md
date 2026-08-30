---
type: 快速上手
title: "OpenWiki 快速上手 — rearch_agent"
description: "rearch_agent 知识库的入口：说明系统是什么、Wiki 如何组织，以及提供一张任务路由表，用于定位变更所归属的源代码、符号、聚焦测试和最小验证。"
tags: [quickstart, navigation]
openwiki:
  roles: [repository]
  change_kinds: [navigation]
verified:
  - by: openwiki/0.4.3
    at: 2026-08-30T09:34:27.074Z
sources:
  - id: openwiki-source-b6de53dbd98682810a0d22dd
    resource: repo://backend/app/agent/config/profile_loader.py
  - id: openwiki-source-61b1044eaa543499e296aef4
    resource: repo://backend/app/agent/context.py
  - id: openwiki-source-b0a17fc9494308297a9d277f
    resource: repo://backend/app/agent/middleware/prompt_compiler_middleware.py
  - id: openwiki-source-da99e0252c3f71a583ce0b81
    resource: repo://backend/app/agent/middleware/rag_prompt_injector_middleware.py
  - id: openwiki-source-be1d78a2f8abe4d10dd814ee
    resource: repo://backend/app/agent/service.py
  - id: openwiki-source-e80de85d123786a60f124628
    resource: repo://backend/app/agent/subagents/sql/tools.py
  - id: openwiki-source-7fef2980ecaa695d2f8d3f90
    resource: repo://backend/app/agent/utils/llama_cpp_token_estimator.py
  - id: openwiki-source-979a5da7c8dfc9bf4d7b96f5
    resource: repo://backend/app/agent/utils/vllm_token_estimator.py
  - id: openwiki-source-4188bfee2e15d969d3152477
    resource: repo://backend/app/config.py
  - id: openwiki-source-181046f9b9fb4eb1d2d76114
    resource: repo://backend/app/routers/chat.py
  - id: openwiki-source-c052fae739a4f7f9af1d35f1
    resource: repo://backend/app/schemas.py
  - id: openwiki-source-41863953653ad4cd47aa60a2
    resource: repo://backend/tests/agent/test_tool_error_contract.py
  - id: openwiki-source-86488ad52172c293ceaa082e
    resource: repo://docs/architecture/adr-model-sampling-profiles.md
  - id: openwiki-source-0f7aec6b703e12a01bb0c167
    resource: repo://docs/architecture/glossary-model-sampling.md
  - id: openwiki-source-1195d204477ba1ef200811b5
    resource: repo://frontend/index.html
  - id: openwiki-source-a65b92db11e257b9aee419ec
    resource: repo://frontend/src/api/chat.ts
  - id: openwiki-source-96bc62ae64beb4d42595fccc
    resource: repo://frontend/src/types/index.ts
  - id: openwiki-source-8387524ace62d9d46eaeb53e
    resource: repo://openspec/changes/phase2-sampling-profiles-stage-c/spec.md
  - id: openwiki-source-498d91cb54f5f142eef1e7ba
    resource: repo://openspec/changes/phase3-thinking-levels/spec.md
generated: { by: "openwiki/0.4.3", at: "2026-08-30T09:34:27.074Z" }
---

# OpenWiki 快速上手 — rearch_agent

**rearch_agent** 是一个生产级数据查询聊天系统：一个 FastAPI + LangGraph **DeepAgent** 后端（一个主协调代理加上一个编译后的 **SQL 领域子代理**）针对 PostgreSQL 分析数据库回答业务问题，具备领域技能、RAG + 三层数据库术语表、结构化 SSE 流、人在回路澄清，以及用于图表/CSV/表格的统一工件存储。前端是一个 Vue 3 + Pinia 单页应用。

## 本 Wiki 的组织方式

- **[架构](architecture/overview.md)** — 运行时拓扑、双重持久化模式，以及代理装配 / 状态 / 子代理 / 中间件 / 工具子系统；基于文件的系统提示模板及其主↔子代理协作契约位于 [代理提示](architecture/agent-prompts.md)。
- **[领域](domain/skills-and-scenarios.md)** — 技能与场景、RAG 与术语表，以及聊天数据模型。
- **[工作流](workflows/streaming-protocol.md)** — 跨组件流程：SSE 流、澄清循环，以及工件旁路通道。
- **[前端](frontend/chat-app.md)** — Vue 单页应用。
- **[运维](operations/deployment-and-testing.md)** — 如何运行、部署和验证。

每个页面都列出其所属源码路径、关键符号、不变量、聚焦测试和变更操作指南，因此你可以无需全仓库搜索即可从意图导航到代码。

## 任务路由表

| 变更区域 / 意图 | Wiki 页面 | 源代码入口 | 关键符号 / 类型 | 聚焦测试 | 最小验证 |
|---|---|---|---|---|---|
| 添加工具 / 加固 SQL 防护 | [工具与 SQL 检查器](architecture/tools-and-sql-linter.md) | `backend/app/agent/subagents/sql/tools.py`, `backend/app/agent/utils/sql_linter.py` | `create_wrapped_query_tool`, `SQLLinter`, `ToolNames` | `tests/agent/test_tools_main_and_subagent_compatibility.py`, `tests/agent/tools/` | `cd backend && python -m pytest tests/agent/test_tools_main_and_subagent_compatibility.py tests/agent/tools -q` |
| 添加领域技能 / 场景 | [技能与场景](domain/skills-and-scenarios.md) | `backend/app/skills/domains/`, `backend/app/routers/scenarios.py` | `reload_skills`, `discover_domains`, `resolve_params` | `tests/test_scenario_quick_panel_api.py` | `cd backend && python -m pytest tests/test_scenario_quick_panel_api.py tests/test_scenario_quick_panel_engine.py -q` |
| 添加中间件 / 变更提示编译 | [中间件流水线](architecture/middleware-pipeline.md) | `backend/app/agent/middleware/`, `backend/app/agent/service.py` | `SkillMiddleware`, `PromptCompilerMiddleware`, `_build_agent_components` | `tests/agent/middleware/`, `tests/agent/vector/sql_lexicon/test_rag_middleware.py` | `cd backend && python -m pytest tests/agent/middleware tests/agent/vector/sql_lexicon/test_rag_middleware.py -q` |
| 切换采样参数 / 思考强度档位 | [采样参数组合与动态注入](architecture/sampling-profiles.md) | `backend/app/agent/config/profile_loader.py`, `backend/app/agent/config/model_sampling_profiles.yaml`, `backend/app/routers/chat.py`, `frontend/src/composables/useChatStream.ts`；设计权威：`docs/architecture/adr-model-sampling-profiles.md`、`docs/architecture/glossary-model-sampling.md`、`openspec/changes/phase2-sampling-profiles-stage-c/spec.md`、`openspec/changes/phase3-thinking-levels/spec.md` | `get_sampling_profile`, `apply_profile_to_model_settings`, `REASONING_EFFORT_TRANSPORT`, `thinking_level_map`, `ThinkingLevel`, `SegmentedControl` | `tests/agent/test_sampling_profile_loader.py`, `tests/agent/middleware/test_prompt_compiler_middleware.py`, `tests/agent/middleware/test_rag_prompt_injector_middleware.py` | `cd backend && python -m pytest tests/agent/test_sampling_profile_loader.py tests/agent/middleware/test_prompt_compiler_middleware.py tests/agent/middleware/test_rag_prompt_injector_middleware.py -q && cd frontend && npx vue-tsc --noEmit` |
| 编辑系统提示 / 主↔子代理协作契约 | [代理提示](architecture/agent-prompts.md) | `backend/app/agent/prompts/main_system_prompt.md`, `backend/app/agent/subagents/sql/base_system_prompt.md`, `backend/app/agent/utils/system_prompt_loader.py` | `SystemPromptLoader`, `_build_main_system_prompt`, `_build_system_prompt` | `tests/agent/test_main_system_prompt.py`, `tests/agent/utils/test_system_prompt_loader.py` | `cd backend && python -m pytest tests/agent/test_main_system_prompt.py tests/agent/utils/test_system_prompt_loader.py -q` |
| 切换或扩展 LLM / 令牌引擎 | [代理服务](architecture/agent-service.md) | `backend/app/agent/llm.py`, `backend/app/agent/service.py`, `backend/app/agent/utils/llama_cpp_token_estimator.py`, `backend/app/agent/utils/vllm_token_estimator.py` | `_create_llm`, `_create_token_estimator`, `ReasoningAwareChatDeepSeek`, `VllmTokenEstimator`, `LlamaCppTokenEstimator`, `TOKEN_ESTIMATOR_ENGINE`（N5 熔断：`/tokenize` 首次 HTTP 失败即熔断，永久退回 `_estimate_fallback_tokens` 保守估算，不再逐请求重试） | `tests/agent/test_chat_deepseek_integration.py`, `tests/agent/test_tool_error_contract.py` | `cd backend && python -m pytest tests/agent/test_chat_deepseek_integration.py tests/agent/test_tool_error_contract.py -q` |
| 添加流事件类型 | [流协议](workflows/streaming-protocol.md) | `backend/app/schemas.py`, `frontend/src/api/chat.ts`, `frontend/src/types/index.ts` | `ChatStreamEvent`, `STREAM_EVENT_TYPES`, `parseStreamEvent` | `tests/test_routers_coverage.py`, `tests/agent/test_subagent_stream_scoping.py` | `cd backend && python -m pytest tests/test_routers_coverage.py -q && cd frontend && npx vue-tsc --noEmit` |
| 添加新的工件类型 | [工件生命周期](workflows/artifact-lifecycle.md) | `backend/app/artifacts/`, `backend/app/routers/artifacts.py` | `ArtifactKind`, `ArtifactStore`, `get_artifact_store` | `tests/agent/test_artifact_store_lifecycle.py`, `tests/test_tool_artifacts_persistence.py` | `cd backend && python -m pytest tests/agent/test_artifact_store_lifecycle.py tests/test_tool_artifacts_persistence.py -q` |
| 变更状态 / 上下文沙箱隔离 | [状态与上下文](architecture/state-and-context.md) | `backend/app/agent/state.py`, `backend/app/agent/context.py` | `CustomState`, `SqlSubAgentState`, `RequestContext` | `tests/agent/test_state_sandboxing_concurrency.py`, `tests/agent/test_context_api_transient_flow.py` | `cd backend && python -m pytest tests/agent/test_state_sandboxing_concurrency.py tests/agent/test_context_api_transient_flow.py -q` |
| 切换 RAG 后端 / 术语表 | [RAG 与术语表](domain/rag-and-lexicon.md) | `backend/app/agent/vector/factory.py`, `backend/app/agent/vector/sql_lexicon/` | `create_business_retriever_and_reranker`, `DatabaseLexiconRetriever` | `tests/agent/vector/`, `tests/agent/test_retriever_async_contract.py` | `cd backend && python -m pytest tests/agent/vector tests/agent/test_retriever_async_contract.py -q` |
| 添加持久化消息字段 | [数据模型与持久化](domain/data-model-and-persistence.md) | `backend/app/models.py`, `backend/app/database.py`, `backend/app/schemas.py` | `ChatMessage`, `create_tables` | `tests/test_tool_artifacts_persistence.py` | `cd backend && python -m pytest tests/test_tool_artifacts_persistence.py -q` |
| 澄清 / 恢复行为 | [澄清流程](workflows/clarification-flow.md) | `backend/app/agent/tools/ask_user_question.py`, `backend/app/routers/chat.py` | `AskUserQuestion`, `QuestionItem`, `stream_message_resume` | `tests/test_routers_coverage.py` | `cd backend && python -m pytest tests/test_routers_coverage.py -q` |
| 前端消息卡片 / 子代理 UI | [聊天应用](frontend/chat-app.md) | `frontend/src/components/chat/`, `frontend/src/stores/messages.ts` | `useMessagesStore`, `SubagentCard`, `reconstructSubagents` | —（无前端单元测试） | `cd frontend && npx vue-tsc --noEmit` |
| 聊天导航 / 问题栏 / 滚动定位 | [聊天应用 — 问题导航栏](frontend/chat-app.md#问题导航栏) | `frontend/src/components/chat/QuestionRail.vue`, `frontend/src/composables/useScrollSpy.ts`, `frontend/src/components/chat/MessageList.vue` | `QuestionRail`, `useScrollSpy`, `UserQuestionItem`, `scrollToMessage` | —（无前端单元测试） | `cd frontend && npx vue-tsc --noEmit` |
| 运行 / 部署 / 配置 | [部署与测试](operations/deployment-and-testing.md) | `docker-compose.yml`, `run_backend.py`, `backend/app/config.py` | `Settings`, `langgraph.json` | `tests/smoke/`（条件性） | `cd backend && python -m pytest -q` |

> 验证说明：聚焦的 `pytest -q` 运行可保持输出简洁，同时保留完整的失败诊断。`integration` 和 `smoke` 层为**条件性**——仅当有可用的实时 Postgres/Milvus/LLM（或正在运行的后端）时才运行；参见 [部署与测试](operations/deployment-and-testing.md)。

## 从哪里开始 / 需要注意什么

- **两条初始化路径必须保持同步**（`_initialize_agent` 与 `_ainitialize_agent`）——请在 `_build_agent_components` 中更改工具/中间件/RAG 装配，使两条路径均受益。
- **瞬态数据通过 Context API 传递，而不是检查点状态**——请将每轮大型载荷放入 `RequestContext`。
- **旁路工件使 LLM 上下文保持精简**——应返回 `Command(update={... tool_artifact})`，而不是原始行。
- **新的流事件需要 3 处前端注册 + 后端联合类型**，否则会被静默丢弃。
- **思考配置注入必须双中间件对称**（主智能体 `RagPromptInjectorMiddleware` + SQL 子智能体 `PromptCompilerMiddleware`）；`/api/chat/resume` 端点不继承思考档位。推理框架切换只需改 `REASONING_EFFORT_TRANSPORT`（ninfer=`top_level` / vLLM ≤0.27.1=`chat_template_kwargs`），见 [采样参数组合与动态注入](architecture/sampling-profiles.md)。
- **仅离线前端**——不使用公共 CDN；本地化字体/库。

## 待办事项

尚未设立专门页面的领域（源码锚点 + 原因）。当支撑源码稳定后再提升为页面。

- **根级代理指令文件与仓库技能库**（`.claude/agents/`、`.agents/skills/`）——面向开发者的 Claude/代理技能定义（例如 `code-explainer`、`code-reviewer`）以及 `AGENTS.md`/`CLAUDE.md` 约定。它们不属于运行时代理 Wiki 的范围，且这些文件由用户编写（本 Wiki 不得编辑 `/AGENTS.md`/`CLAUDE.md`）；它们所描述的运行时子代理已在 [SQL 子代理](architecture/subagent-sql.md) 中记录。
- **仅文档型意图报告**（`docs/deepagent/`、`docs/multiagent_sidechannel/`、`docs/llamaindex_rag/`、`docs/superpowers/`）——仅链接的设计意图；本 Wiki 在相关运行时页面中引用它们，而不是复述。只有当某个具体设计决策变得关键时，才重新考虑作为总结页面。（例外：`docs/superpowers/` 下的问题栏规范/计划已在代码中实现，并由 [聊天应用 — 问题导航栏](frontend/chat-app.md#问题导航栏) 覆盖。）
- **SubAgent 注册表 / 工厂模式**（规范：`docs/superpowers/specs/2026-08-23-multi-agent-prompt-and-architecture-optimization.md`）——计划重构 `backend/app/agent/subagents/`（注册表 `__init__.py`、`BaseSubAgentFactory`、按领域的 `factory.py`），以及 `knowledge_doc_agent` / `iot_device_agent` 专业代理；**尚未在代码中**（`subagents/__init__.py` 是注释占位符，`service.py` 仍然内联构建 SQL 子代理）。已在 [代理提示](architecture/agent-prompts.md) 中简要记录；待代码落地后提升为完整架构页面。
