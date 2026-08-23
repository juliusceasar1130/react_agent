---
type: 组件
title: "智能体工具与 SQL 安全层"
description: "SQL 子智能体的工具表面：包装后的 sql_db_query 保护管道、数据库词汇表工具，以及旁路通道图表/CSV 产物工具，外加两层 SQL 安全机制（正则表达式 + AST 检查器）。"
tags: [architecture, tools, sql, security]
openwiki:
  roles: [architecture, security]
  change_kinds: [tooling, security]
  source_paths: [backend/app/agent/subagents/sql/tools.py, backend/app/agent/tools/chart_artifact_tool.py, backend/app/agent/tools/csv_export_tool.py, backend/app/agent/utils/sql_linter.py, backend/app/agent/constants.py]
  symbols: [create_wrapped_query_tool, create_chart_artifact_tool, create_csv_export_tool, validate_readonly_query, SQLLinter, EXCLUDED_TOOLS]
  test_paths: [backend/tests/agent/test_tools_main_and_subagent_compatibility.py, backend/tests/agent/tools/test_sql_lexicon_tools.py]
  invariants:
    - All LLM-facing tools set handle_tool_error=True and raise ToolException with an Error-space prefixed message so ReAct can self-heal.
    - Chart and CSV tools return a Command(update={messages, tool_artifact}) side channel instead of dumping rows into the LLM context.
    - The wrapped sql_db_query is skill-gated and optionally linter-gated before execution.
  validation_commands: ["cd backend && python -m pytest tests/agent/test_tools_main_and_subagent_compatibility.py tests/agent/tools -q"]
---

# 智能体工具与 SQL 安全层

工具层是 [SQL 子智能体](subagent-sql.md) 的具体工作表面。工厂位于 `backend/app/agent/subagents/sql/tools.py` 和 `backend/app/agent/tools/`；两层安全引擎是 `backend/app/agent/utils/sql_linter.py`；魔法字符串常量位于 `backend/app/agent/constants.py`（`ToolNames`、`EXCLUDED_TOOLS`）。

## 受保护的查询工具

`create_wrapped_query_tool`（位于 `subagents/sql/tools.py`）包装来自 `SQLDatabaseToolkit` 的默认 `sql_db_query`。在执行前，它会执行以下控制：

1. **技能门禁** — `required_skill` 必须出现在 `runtime.state["skills_loaded"]` 中（由 `load_skill` 通过 `SqlSubAgentState` 设置，参见 [state-and-context](state-and-context.md)）。如果不匹配，则返回 `Error: 请先使用 load_skill(...)` 字符串，而不是抛出异常。
2. **SQL 检查器** — 当 `settings.sql_linter_enabled` 为真时，先运行 `validate_readonly_query(query, custom_table_info)`，并抛出 `SQLLintException`，随后转换为 `ToolException`。
3. **检查器模式** — 当 `settings.sql_checker_mode == "safety"` 时，可选地运行 `sql_db_query_checker`。
4. **执行并规范化** — 使用 `db.run_no_throw`（并设置 `include_columns=True`），然后清理 ISO-8601 日期和 Decimal→float 类型。
5. **截断与旁路通道** — 强制行数上限（`sql_result_hard_limit`，或通过 sqlglot AST 检测到的纯维度查询使用 `dimension_result_hard_limit`）。该工具返回 `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})`。参见 [artifact-lifecycle](../workflows/artifact-lifecycle.md)。

## SQL 检查器

`backend/app/agent/utils/sql_linter.py` 实现了 `SQLLinter` — 它是针对 sqlglot 解析查询的 `BaseLintRule` AST 规则注册表（只读强制执行、子查询/CTE 深度上限、允许的模式检查）。`SQLLinter.register` 会遵循 `settings.sql_linter_disabled_rules` 和 `rules_severity_override`。当检查器阻止查询时，它会发出带有编号违规项和修复建议的 `X-SQL-LINTER-STATUS: FAILED`。

## 旁路通道产物工具

- `create_chart_artifact_tool`（`backend/app/agent/tools/chart_artifact_tool.py`）→ `build_chart_artifact`。它将 `chart_spec` 产物写入 `ArtifactStore`，并返回 `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})`，使图表配置能够到达 UI，而不占用 LLM 上下文。`ChartSeriesInput` 会校验系列定义（类别配对、y 轴、颜色）。
- `create_csv_export_tool`（`backend/app/agent/tools/csv_export_tool.py`）→ `export_to_csv`。它将大型 SQL 结果流式写入 `file_export` 产物，并带有 OOM 熔断器保护和临时来源自清理；返回相同的 `Command` 旁路通道。

两者都会读取 `runtime: ToolRuntime[RequestContext, SqlSubAgentState]` 并返回 `Command(update={...})`；原生签名约定（纯 `runtime: ToolRuntime[...]` 参数，绝不使用 `| None = None` 联合类型）是提交 48d5da7 修复的内容，以避免 Pydantic 在序列化 `CallableSchema` 时崩溃。

## 错误契约（仓库级不变量，来自 `AGENTS.md`）

1. 预期的业务/参数错误：使用 `raise ToolException("Error: ...")` — 绝不使用裸的 `ValueError`/`Exception`，否则会导致图崩溃。
2. 每个面向 LLM 的工具都会设置 `tool.handle_tool_error = True`。
3. 错误文本必须以 `"Error: "` 开头，以便 [PromptCompilerMiddleware](middleware-pipeline.md) 能够预先扫描失败调用并安全地折叠历史上下文。
4. LLM 可见参数通过 Pydantic `args_schema` 声明；框架注入参数使用原生 `runtime: ToolRuntime[...]` 签名。

## 不变量与测试

- 图表/CSV 工具在 `CustomState`（主智能体）和 `SqlSubAgentState`（子智能体）下均可工作，并且 LLM 可见的 `args` 永远不会泄露注入的 `runtime`：`backend/tests/agent/test_tools_main_and_subagent_compatibility.py`（`test_build_chart_artifact_main_agent_invoke`、`test_export_to_csv_main_and_subagent_invoke`、`test_tools_injection_contract_and_llm_schema`、`test_chart_series_pydantic_validation_error_contract`）。
- 词汇表工具行为：`backend/tests/agent/tools/test_sql_lexicon_tools.py`。

## 变更配方：添加或强化 SQL 防护规则

1. 在 `backend/app/agent/utils/sql_linter.py` 中添加 `BaseLintRule` 子类；在 `SQLLinter` 中注册它（遵循 `settings.sql_linter_disabled_rules`）。
2. 如果规则应该是硬性阻止，则抛出 `SQLLintException`（已在 `create_wrapped_query_tool` 中转换为 `ToolException`）。
3. 保持 `handle_tool_error = True` 和 `Error: ` 前缀，使 LLM 能够自我修复，而不是图崩溃。
4. 使用上述工具兼容性测试进行验证；检查器目前没有专用测试文件，因此如果你更改规则行为，请在 `backend/tests/agent/` 下添加一个聚焦用例，模仿现有的 `test_..._linter` 风格。