---
type: Component
title: "Agent Tools & SQL Safety Layer"
description: "The tool surface of the SQL subagent: wrapped sql_db_query guard pipeline, DB-lexicon tools, and the side-channel chart/CSV artifact tools, plus the two-layer SQL safety (regex + AST linter)."
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

# Agent Tools & SQL Safety Layer

The tool layer is the concrete work surface of the [SQL subagent](subagent-sql.md). Factories live in `backend/app/agent/subagents/sql/tools.py` and `backend/app/agent/tools/`; the two-layer safety engine is `backend/app/agent/utils/sql_linter.py`; magic-string constants are `backend/app/agent/constants.py` (`ToolNames`, `EXCLUDED_TOOLS`).

## Guarded query tool

`create_wrapped_query_tool` (in `subagents/sql/tools.py`) wraps the stock `sql_db_query` from `SQLDatabaseToolkit`. Before execution it enforces:

1. **Skill gate** — `required_skill` must appear in `runtime.state["skills_loaded"]` (set by `load_skill` through `SqlSubAgentState`, see [state-and-context](state-and-context.md)). On mismatch it returns an `Error: 请先使用 load_skill(...)` string, not an exception.
2. **SQL Linter** — when `settings.sql_linter_enabled`, `validate_readonly_query(query, custom_table_info)` runs first and raises `SQLLintException`, converted to `ToolException`.
3. **Checker mode** — optional `sql_db_query_checker` run when `settings.sql_checker_mode == "safety"`.
4. **Execute + normalize** — `db.run_no_throw` (with `include_columns=True`), then ISO-8601 date and Decimal→float cleaning.
5. **Truncation + side channel** — hard row limit (`sql_result_hard_limit`, or `dimension_result_hard_limit` for pure dimension queries detected via sqlglot AST). The tool returns `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})`. See [artifact-lifecycle](../workflows/artifact-lifecycle.md).

## SQL Linter

`backend/app/agent/utils/sql_linter.py` implements `SQLLinter` — a registry of `BaseLintRule` AST rules over sqlglot-parsed queries (read-only enforcement, subquery/CTE depth caps, allowed-schema checks). `SQLLinter.register` honors `settings.sql_linter_disabled_rules` and `rules_severity_override`. The linter emits `X-SQL-LINTER-STATUS: FAILED` with numbered violations and fix suggestions when it blocks a query.

## Side-channel artifact tools

- `create_chart_artifact_tool` (`backend/app/agent/tools/chart_artifact_tool.py`) → `build_chart_artifact`. Writes a `chart_spec` artifact to the `ArtifactStore` and returns a `Command(update={"messages": [ToolMessage], "tool_artifact": {...}})` so the chart config reaches the UI without occupying LLM context. `ChartSeriesInput` validates series definitions (category pairs, y-axis, colors).
- `create_csv_export_tool` (`backend/app/agent/tools/csv_export_tool.py`) → `export_to_csv`. Streams a large SQL result to a `file_export` artifact with OOM-circuit-breaker protection and temp-source self-cleanup; returns the same `Command` side channel.

Both read `runtime: ToolRuntime[RequestContext, SqlSubAgentState]` and return `Command(update={...})`; the native-signature convention (a pure `runtime: ToolRuntime[...]` parameter, never a `| None = None` union) is what commit 48d5da7 fixed so Pydantic doesn't crash on `CallableSchema` serialization.

## Error contract (repository-wide invariant, from `AGENTS.md`)

1. Expected business/param errors: `raise ToolException("Error: ...")` — never a bare `ValueError`/`Exception`, which would crash the graph.
2. Every LLM-facing tool sets `tool.handle_tool_error = True`.
3. Error text must start with `"Error: "` so [PromptCompilerMiddleware](middleware-pipeline.md) can pre-scan failed calls and safely collapse historical context.
4. LLM-visible params declared via Pydantic `args_schema`; framework-injected params use the native `runtime: ToolRuntime[...]` signature.

## Invariants & tests

- Chart/CSV tools work under both `CustomState` (main) and `SqlSubAgentState` (subagent), and the LLM-visible `args` never leak the injected `runtime`: `backend/tests/agent/test_tools_main_and_subagent_compatibility.py` (`test_build_chart_artifact_main_agent_invoke`, `test_export_to_csv_main_and_subagent_invoke`, `test_tools_injection_contract_and_llm_schema`, `test_chart_series_pydantic_validation_error_contract`).
- Lexicon tool behavior: `backend/tests/agent/tools/test_sql_lexicon_tools.py`.

## Change recipe: add or harden a SQL guard rule

1. Add a `BaseLintRule` subclass in `backend/app/agent/utils/sql_linter.py`; register it in `SQLLinter` (respect `settings.sql_linter_disabled_rules`).
2. If the rule should be a hard block, raise `SQLLintException` (already converted to `ToolException` in `create_wrapped_query_tool`).
3. Keep `handle_tool_error = True` and the `Error: ` prefix so the LLM self-heals instead of the graph crashing.
4. Validate with the tool-compatibility tests above; the linter has no dedicated test file today, so add a focused case under `backend/tests/agent/` mirroring the existing `test_..._linter` style if you change rule behavior.
