---
type: 组件
title: "SQL 域子智能体（sql_domain_agent）"
description: "已编译的 SQL 专家子智能体：其工具工厂集合、被封装的 sql_db_query 守卫流水线、系统提示词，以及如何作为 CompiledSubAgent 打包给主 DeepAgent。"
tags: [architecture, subagent, sql, deepagent]
openwiki:
  roles: [architecture, domain]
  change_kinds: [lifecycle, tooling]
  source_paths: [backend/app/agent/subagents/sql/tools.py, backend/app/agent/subagents/sql/prompts.py, backend/app/agent/subagents/sql/base_system_prompt.md]
  symbols: [create_wrapped_query_tool, create_sql_example_search_tool, create_db_value_lexicon_tool, create_db_row_lexicon_tool, create_db_table_schema_tool, _build_system_prompt]
  test_paths: [backend/tests/agent/tools/test_sql_lexicon_tools.py, backend/tests/agent/test_agent_component_boundaries.py]
  invariants:
    - sql_db_query refuses to run unless required_skill is present in runtime.state skills_loaded.
    - The subagent exclusively owns SkillMiddleware and PromptCompilerMiddleware.
    - Prompt contract: ambiguous input is self-healed via the DB lexicon probes before AskUserQuestion; every numeric answer ends with a standalone `数据来源：表名，查询时间：...` line.
  validation_commands: ["cd backend && python -m pytest tests/agent/tools/test_sql_lexicon_tools.py tests/agent/test_agent_component_boundaries.py -q"]
---

# SQL 域子智能体（`sql_domain_agent`）

`backend/app/agent/subagents/sql/` 包含主 DeepAgent 委派数据库工作的领域专家。它在 [agent-service](agent-service.md) 中通过 `create_agent(...)` 构建，并作为 `CompiledSubAgent(name="sql_domain_agent", description="【SQL 数据查询分析专家子智能体】...")` 封装。子智能体是 LLM 隐式路由的目标——没有显式主管分类器（这是 `docs/deepagent/architecture_review_report.md` 中记录的有意决策：通过避免额外 LLM 路由调用来保持低 TTFT）。

## 工具工厂集合

所有工厂位于 `backend/app/agent/subagents/sql/tools.py`，并通过 `backend/app/agent/tools/__init__.py` 重新导出：

| 工厂 | LLM 可见工具 | 行为 |
|---|---|---|
| `create_wrapped_query_tool` | `sql_db_query` | 技能门控 + Linter 门控的查询执行（详见 [tools-and-sql-linter](tools-and-sql-linter.md)） |
| `create_sql_example_search_tool` | `search_saved_correct_tool_uses` | 从业务检索器中检索黄金 SQL 示例（`doc_type="sql_example"`，按 `required_skill` 限定领域范围） |
| `create_db_value_lexicon_tool` | `search_db_value_lexicon` | 用于纠错的列值去重词典查找 |
| `create_db_row_lexicon_tool` | `search_db_row_lexicon` | 行级词典查找 |
| `create_db_table_schema_tool` | `search_db_table_schema` | DDL 骨架查找 |

当检索器缺失时，词典工具返回 `"Error: Database lexicon retriever is not initialized or disabled."`——这一相同的 `Error: ` 前缀契约使 [PromptCompilerMiddleware](middleware-pipeline.md) 的失败折叠机制得以工作。

## 受控查询流水线

`create_wrapped_query_tool` 封装标准 `sql_db_query` 工具，并按顺序强制执行以下检查（完整细节见 [tools-and-sql-linter](tools-and-sql-linter.md)）：

1. **技能门控** —— `required_skill` 必须存在于 `runtime.state["skills_loaded"]`（由 `load_skill` 通过 `SqlSubAgentState` 填充，参见 [state-and-context](state-and-context.md)）。
2. **SQL Linter** —— 当 `settings.sql_linter_enabled` 时运行 `validate_readonly_query`（参见 `backend/app/agent/utils/sql_linter.py`）。
3. **检查器模式** —— 当 `settings.sql_checker_mode == "safety"` 时可选运行 `sql_db_query_checker`。
4. **执行 + 规范化** —— 清理 ISO-8601 日期，Decimal→float，然后进行硬行数限制截断（`sql_result_hard_limit` / `dimension_result_hard_limit`），并附带预览 + 自愈指引块。
5. **旁路通道** —— 返回 `Command(update={"messages": [ToolMessage], "tool_artifact": {...query_result...}})`，使完整结果集到达 UI 而不占用 LLM 上下文（参见 [artifact-lifecycle](../workflows/artifact-lifecycle.md)）。

## 系统提示词

- `base_system_prompt.md`（SQL 专家提示词，`settings.system_prompt_path` 默认值）+ `prompts.py::_build_system_prompt(db)`，它通过共享的 `SystemPromptLoader` 加载并渲染 `{dialect}` / `{top_k}` `PromptTemplate` 变量——此配对的主智能体侧以及完整加载路径记录在 [agent-prompts](agent-prompts.md)。
- 子智能体的提示词是 `SkillMiddleware` / `PromptCompilerMiddleware` 在每次模型调用时编译的内容（参见 [middleware-pipeline](middleware-pipeline.md)）。
- 当前契约要点：角色为“120JPH 喷漆车间 Data Agent”；输入验证遵循 **自愈优先**——在允许 `AskUserQuestion` 之前，必须使用 `search_db_value_lexicon` / `search_db_row_lexicon` 探测模糊术语（参见 [clarification-flow](../workflows/clarification-flow.md) 中的两级拆分）；图表建议以及 `数据来源：` 页脚在提示词 §4 中定义，是主智能体展示协议的透传输入。

## 不变量与测试

- 子智能体独占 `SkillMiddleware` + `PromptCompilerMiddleware` —— `backend/tests/agent/test_agent_component_boundaries.py`。
- 词典工具行为 —— `backend/tests/agent/tools/test_sql_lexicon_tools.py`（`test_db_value_lexicon_tool`、`test_db_row_lexicon_tool`、`test_db_table_schema_tool`）。
- 图表/CSV 工具必须同时支持 `CustomState`（主）和 `SqlSubAgentState`（子智能体）—— `backend/tests/agent/test_tools_main_and_subagent_compatibility.py`。

## 变更配方：向 SQL 子智能体添加新工具

1. 在 `backend/app/agent/subagents/sql/tools.py` 中使用 `ToolRuntime[RequestContext, SqlSubAgentState]` 原生签名约定定义工具（参见 [tools-and-sql-linter](tools-and-sql-linter.md) —— 在运行时参数上使用 `| None = None` 联合类型会破坏 Pydantic JSON 模式生成）。
2. 从 `backend/app/agent/tools/__init__.py` 重新导出（`__all__` + 导入），然后在 `backend/app/agent/service.py` 的 `_prepare_tools` 中注册。
3. 预期错误：抛出 `raise ToolException("Error: ...")`，并设置 `handle_tool_error = True`，以便 `PromptCompilerMiddleware` 可以折叠失败调用（契约见 `AGENTS.md`）。
4. 如果工具生成面向用户的数据，请返回 `Command(update={... "tool_artifact": ...})`，并将负载类型添加到 [artifact-lifecycle](../workflows/artifact-lifecycle.md) 关注事项中。
5. 验证：`cd backend && python -m pytest tests/agent/test_tools_main_and_subagent_compatibility.py tests/agent/tools -q`。