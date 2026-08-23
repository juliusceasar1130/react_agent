---
type: 组件
title: "智能体中间件流水线"
description: "LangChain 智能体中间件：技能注入、单轮业务 RAG + 词表检索写入 Context API、上下文窗口告警、提示词编译器（系统消息合并）以及 RAG 提示词注入。"
tags: [architecture, middleware, rag, prompt]
openwiki:
  roles: [architecture]
  change_kinds: [lifecycle]
  source_paths: [backend/app/agent/middleware/__init__.py, backend/app/agent/middleware/skill_middleware.py, backend/app/agent/middleware/rag_middleware.py, backend/app/agent/middleware/prompt_compiler_middleware.py, backend/app/agent/middleware/context_warning_middleware.py, backend/app/agent/middleware/rag_prompt_injector_middleware.py]
  symbols: [SkillMiddleware, BusinessRagMiddleware, PromptCompilerMiddleware, ContextWarningMiddleware, RagPromptInjectorMiddleware, ULTIMATE_DELETION_TOOLS, COLLAPSIBLE_TOOLS]
  test_paths: [backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py, backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py, backend/tests/agent/test_context_api_transient_flow.py]
  invariants:
    - RAG 文档与词表 DDL 经由 RequestContext（Context API）流转，绝不经过检查点状态。
    - PromptCompilerMiddleware 将所有系统消息合并为单一的首位系统消息，以满足严格的本地推理引擎（vLLM）。
  validation_commands: ["cd backend && python -m pytest tests/agent/middleware tests/agent/vector/sql_lexicon/test_rag_middleware.py -q"]
openwiki_translation_pending: "zh-CN"
---

# 智能体中间件流水线

`backend/app/agent/middleware/` 承载塑形每次模型调用的 `AgentMiddleware` 子类。它们在 [代理服务](agent-service.md) 中组装；导出列表见 `backend/app/agent/middleware/__init__.py`。

| 中间件 | 负责内容 | 挂载位置 |
|---|---|---|
| `SkillMiddleware` | 注册 `load_skill` / `load_scenario` 工具；将可用技能目录 + 当前领域 DDL 注入提示词；`before_agent` 将 `skills_loaded` 收窄到当前技能 | 仅 SQL 子智能体（见 [subagent-sql](subagent-sql.md)） |
| `BusinessRagMiddleware` | 单轮检索：`retriever.aretrieve`（+ 可选重排器）加数据库词表 `retrieve_all`，随后将 `rag_context` / `rag_query` / `lexicon_context` 写入 `runtime.context`（Context API），出错时降级为空 | 主智能体 |
| `RagPromptInjectorMiddleware` | 读取 `RequestContext.rag_context`，并在 pre-model 时刻将检索到的 RAG 文本注入系统消息 | 主智能体 |
| `PromptCompilerMiddleware` | 将静态系统提示词 + 当前技能 DDL + RAG + 系统日期合并为单一首位系统消息；折叠/删除陈旧工具调用历史（`ULTIMATE_DELETION_TOOLS`、`COLLAPSIBLE_TOOLS`） | SQL 子智能体 |
| `ContextWarningMiddleware` | 估算输入 token（经由配置的 token 估算器），在接近窗口上限时发出建议新开会话的 `context_warning` 载荷 | 主智能体 |

## 检索如何避免重复劳动

该设计是**单次检索、深拷贝继承**模型（规范见 `docs/deepagent/rag_single_retrieval_spec.md`）：`BusinessRagMiddleware` 在主智能体入口点执行一次，`deepagents` 子图机制深拷贝上下文，使子智能体继承同一轮的 RAG/词表结果而无需重新查询。这就是为何检索挂载在主智能体上，而提示词编译发生在子智能体内。

## 提示词编译器细节

`PromptCompilerMiddleware`（位于 `backend/app/agent/middleware/prompt_compiler_middleware.py`）解决了严格本地推理引擎（如 vLLM）对多系统消息抛出的 400 错误。它在计数/编译前物理地清空所有 `system` 消息并合并到索引 0。`ULTIMATE_DELETION_TOOLS` 集合（三个 `search_db_*_lexicon` 工具）与 `COLLAPSIBLE_TOOLS` 集合控制哪些历史工具调用被物理删除、哪些被折叠。

## 不变量与测试

- RAG 中间件 Context-API 注入且零状态污染：`backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py`（`test_business_rag_middleware_abefore_model`、`test_business_rag_middleware_exception_handling`）与 `backend/tests/agent/test_context_api_transient_flow.py`。
- RAG 提示词注入器从 `RequestContext` 读取、为空时不操作：`backend/tests/agent/middleware/test_rag_prompt_injector_middleware.py`（`test_rag_prompt_injector_injects_rag_text_into_system_message`、`test_rag_prompt_injector_noop_when_no_lexicon_context`）。
- 子智能体 DDL 提示词编译：`backend/tests/agent/test_agent_component_boundaries.py::test_sql_subagent_skill_middleware_loading_and_prompt_compilation`。

## 变更配方：添加新中间件

1. 在 `backend/app/agent/middleware/` 中继承 `AgentMiddleware`；从 `__init__.py` 导出（`__all__`）。
2. 接入 `backend/app/agent/service.py::_build_agent_components` 中正确的列表 —— `subagent_middleware_list`（领域/技能）与 `main_middleware_list`（长会话、RAG、上下文告警）。
3. 若需读取瞬态每轮数据，从 `runtime.context`（`RequestContext`）读取而非状态 —— 参见 [state-and-context](state-and-context.md)。
4. 用上述中间件 + RAG 测试验证。
