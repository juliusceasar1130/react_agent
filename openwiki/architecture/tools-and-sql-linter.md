---
type: "参考"
title: "智能体工具与 SQL 安全层"
openwiki_generated: true
verified:
  - by: openwiki/0.4.3
    at: 2026-08-30T09:34:27.074Z
sources:
  - id: openwiki-source-ea918002408f3534df115999
    resource: repo://backend/app/agent/constants.py
  - id: openwiki-source-b0a17fc9494308297a9d277f
    resource: repo://backend/app/agent/middleware/prompt_compiler_middleware.py
  - id: openwiki-source-be1d78a2f8abe4d10dd814ee
    resource: repo://backend/app/agent/service.py
  - id: openwiki-source-e80de85d123786a60f124628
    resource: repo://backend/app/agent/subagents/sql/tools.py
  - id: openwiki-source-b0992035c8f521ea950e3724
    resource: repo://backend/app/agent/tools/chart_artifact_tool.py
  - id: openwiki-source-7b96292747d956f229a15605
    resource: repo://backend/app/agent/tools/csv_export_tool.py
  - id: openwiki-source-3c31ce63216574dc7def4ebe
    resource: repo://backend/app/agent/tools/skill_tools.py
  - id: openwiki-source-6e51901fcd11673d52547a34
    resource: repo://backend/app/agent/utils/sql_linter.py
  - id: openwiki-source-41863953653ad4cd47aa60a2
    resource: repo://backend/tests/agent/test_tool_error_contract.py
  - id: openwiki-source-3209975ff5dfe11635193cae
    resource: repo://backend/tests/agent/test_tools_main_and_subagent_compatibility.py
  - id: openwiki-source-7a414bbb6740a90f9ad65765
    resource: repo://backend/tests/agent/tools/test_sql_lexicon_tools.py
  - id: openwiki-source-98e429bbd2f92bd04b4796ee
    resource: repo://changelog.md
generated: { by: "openwiki/0.4.3", at: "2026-08-30T09:34:27.074Z" }
---


# 智能体工具与 SQL 安全层

工具层是 [SQL 子智能体](subagent-sql.md) 的具体工作表面。工厂位于 `backend/app/agent/subagents/sql/tools.py` 和 `backend/app/agent/tools/`；两层安全引擎是 `backend/app/agent/utils/sql_linter.py`；魔法字符串常量位于 `backend/app/agent/constants.py`（`ToolNames`、`EXCLUDED_TOOLS`）。所有工具在 `backend/app/agent/service.py::_prepare_tools` 中装配进子智能体，并统一遵守 [AGENTS.md](../../../AGENTS.md) 的错误契约（见下文 [错误契约](#错误契约仓库级不变量来自-agentsmd)）。

## 受保护的查询工具

`create_wrapped_query_tool`（位于 `subagents/sql/tools.py`）包装来自 `SQLDatabaseToolkit` 的默认 `sql_db_query`。在执行前，它会执行以下控制：

1. **技能门禁** — `required_skill` 必须出现在 `runtime.state["skills_loaded"]` 中（由 `load_skill` 通过 `SqlSubAgentState` 设置，参见 [state-and-context](state-and-context.md)）。如果不匹配，则返回 `Error: 请先使用 load_skill(...)` 字符串，而不是抛出异常。
2. **SQL 检查器** — 当 `settings.sql_linter_enabled` 为真时，先运行 `validate_readonly_query(query, custom_table_info)`，并抛出 `SQLLintException`，随后转换为 `ToolException`。
3. **检查器模式** — 当 `settings.sql_checker_mode == "safety"` 时，可选地运行 `sql_db_query_checker`。
4. **执行并规范化** — 使用 `db.run_no_throw`（并设置 `include_columns=True`），然后清理 ISO-8601 日期和 Decimal→float 类型。
5. **截断与旁路通道** — 强制行数上限（`sql_result_hard_limit`，或通过 sqlglot AST 检测到的纯维度查询使用 `dimension_result_hard_limit`）。该工具返回 `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})`。参见 [artifact-lifecycle](../workflows/artifact-lifecycle.md)。

## SQL 检查器

`backend/app/agent/utils/sql_linter.py` 实现了 `SQLLinter` — 它是针对 sqlglot 解析查询的 `BaseLintRule` AST 规则注册表（只读强制执行、子查询/CTE 深度上限、允许的模式检查）。`SQLLinter.register` 会遵循 `settings.sql_linter_disabled_rules` 和 `rules_severity_override`。当检查器阻止查询时，它会发出带有编号违规项和修复建议的 `X-SQL-LINTER-STATUS: FAILED`。

`validate_readonly_query` 是两层安全机制的统一入口：第一道是**无条件正则物理阻断**（`FORBIDDEN_SQL_PATTERN` 拦截 INSERT/UPDATE/DELETE/TRUNCATE/GRANT 等关键字，即使 `sql_linter_enabled` 关闭也生效）；第二道是 **11 条 AST 规则**（DML/DDL、堆叠多语句、schema 白名单、`SELECT *`、JOIN 列前缀、子查询深度、CTE 数量、JOIN 扇出、事件表非去重 COUNT、标量子查询、NOT IN）。sqlglot 解析失败时退避为正则 + 多语句校验。

## 旁路通道产物工具

- `create_chart_artifact_tool`（`backend/app/agent/tools/chart_artifact_tool.py`）→ `build_chart_artifact`。它将 `chart_spec` 产物写入 `ArtifactStore`，并返回 `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})`，使图表配置能够到达 UI，而不占用 LLM 上下文。`ChartSeriesInput` 会校验系列定义（类别配对、y 轴、颜色）。
- `create_csv_export_tool`（`backend/app/agent/tools/csv_export_tool.py`）→ `export_to_csv`。它将大型 SQL 结果流式写入 `file_export` 产物，并带有 OOM 熔断器保护（`sql_export_max_rows` 超限即删除半成品文件）和临时来源自清理；返回相同的 `Command` 旁路通道。

两者都会读取 `runtime: ToolRuntime[RequestContext, SqlSubAgentState]` 并返回 `Command(update={...})`；原生签名约定（纯 `runtime: ToolRuntime[...]` 参数，绝不使用 `| None = None` 联合类型）是提交 48d5da7 修复的内容，以避免 Pydantic 在序列化 `CallableSchema` 时崩溃。

## 错误契约（仓库级不变量，来自 `AGENTS.md`）

1. 预期的业务/参数错误：使用 `raise ToolException("Error: ...")` — 绝不使用裸的 `ValueError`/`Exception`，否则会导致图崩溃。
2. 每个面向 LLM 的工具都会设置 `tool.handle_tool_error = True`。**N6 契约**（2026-08-30 变更集）把这一开关钉死在所有工具工厂上：包装后的 `sql_db_query`、`search_saved_correct_tool_uses`、三个 `db_*_lexicon` 词典工具（`search_db_value_lexicon` / `search_db_row_lexicon` / `search_db_table_schema`），以及图表/CSV 工厂（`build_chart_artifact` / `export_to_csv`）；技能工具 `load_skill` / `load_scenario` 亦带此开关。其中 `search_saved_correct_tool_uses`、词典三件套、`load_skill`、`load_scenario` 六把由 N6 补上（异常转 `ToolMessage(status="error")` 回喂模型，保证 ReAct 闭环自愈），`sql_db_query` 与图表/CSV 工厂此前已携带。
3. 错误文本必须以 `"Error: "` 开头，以便 [PromptCompilerMiddleware](middleware-pipeline.md) 能够预先扫描失败调用并安全地折叠历史上下文。N6 同时为 `sql_db_query` 的语法检查失败分支和三个词典工具的检索失败文案补上了 `"Error: "` 前缀。中间件的 Stage 2 预扫描（`_stage_prescan_failures` / `_DELETION_TARGET_CONFIG`）对 `sql_db_query` / `build_chart_artifact` / `export_to_csv` 依赖两个运行时标记识别失败：`X-SQL-LINTER-STATUS: FAILED`（linter 拦截，出自 `LintResult.format_error_message`）或 `Error:` 运行时头；三个 `search_db_*_lexicon` 工具在滑动窗口外则经由 `ULTIMATE_DELETION_TOOLS` 无条件物理删除，窗口内的成功调用由 `COLLAPSIBLE_TOOLS` 折叠为占位符。
4. LLM 可见参数通过 Pydantic `args_schema` 声明；框架注入参数使用原生 `runtime: ToolRuntime[...]` 签名。

## 不变量与测试

- 图表/CSV 工具在 `CustomState`（主智能体）和 `SqlSubAgentState`（子智能体）下均可工作，并且 LLM 可见的 `args` 永远不会泄露注入的 `runtime`：`backend/tests/agent/test_tools_main_and_subagent_compatibility.py`（`test_build_chart_artifact_main_agent_invoke`、`test_export_to_csv_main_and_subagent_invoke`、`test_tools_injection_contract_and_llm_schema`、`test_chart_series_pydantic_validation_error_contract`）。
- 词汇表工具行为：`backend/tests/agent/tools/test_sql_lexicon_tools.py`。
- **N6 错误契约聚焦回归**：`backend/tests/agent/test_tool_error_contract.py` —— `test_lexicon_tools_error_prefix_and_handle_flag` 用伪造的抛异常检索器断言三个 `db_*_lexicon` 工具 `handle_tool_error is True` 且失败输出以 `"Error: "` 开头；`test_skill_tools_handle_flag` 断言 `load_skill` / `load_scenario` 的开关。同一文件还回归 N5 的 token 估算器 404 熔断（`test_vllm_estimator_breaker_on_http_failure` / `test_llama_cpp_estimator_breaker_on_http_failure`，断言熔断后 `fake.post_count == 1`，不再发出 tokenize 请求），参见 [agent-service](agent-service.md) 的熔断契约。

## 变更配方：添加或强化 SQL 防护规则

1. 在 `backend/app/agent/utils/sql_linter.py` 中添加 `BaseLintRule` 子类；在 `SQLLinter` 中注册它（遵循 `settings.sql_linter_disabled_rules`）。
2. 如果规则应该是硬性阻止，则抛出 `SQLLintException`（已在 `create_wrapped_query_tool` / `build_chart_artifact` / `export_to_csv` 中转换为 `ToolException`）。
3. 保持 `handle_tool_error = True` 和 `Error: ` 前缀，使 LLM 能够自我修复，而不是图崩溃。新增工具同样必须在工厂内显式设置 `handle_tool_error = True`，并以 `raise ToolException("Error: ...")`（或返回 `"Error: ..."` 字符串）作为唯一失败出口。
4. 使用上述工具兼容性测试与 `tests/agent/test_tool_error_contract.py` 验证。linter 规则目前仍无专用测试文件，因此如果你更改规则行为，请在 `backend/tests/agent/` 下添加一个聚焦用例，模仿现有的 `test_..._linter` 风格；错误契约本身的回归由 `test_tool_error_contract.py` 承担。
