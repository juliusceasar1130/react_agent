---
type: Component
title: "SQL Domain Subagent (sql_domain_agent)"
description: "The compiled SQL expert subagent: its tool factory set, wrapped sql_db_query guard pipeline, system prompt, and how it is packaged as a CompiledSubAgent for the main DeepAgent."
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
  validation_commands: ["cd backend && python -m pytest tests/agent/tools/test_sql_lexicon_tools.py tests/agent/test_agent_component_boundaries.py -q"]
---

# SQL Domain Subagent (`sql_domain_agent`)

`backend/app/agent/subagents/sql/` holds the domain expert the main DeepAgent delegates database work to. It is built in [agent-service](agent-service.md) via `create_agent(...)` and wrapped as `CompiledSubAgent(name="sql_domain_agent", description="【SQL 数据查询分析专家子智能体】...")`. The subagent is what the LLM routes to implicitly — no explicit supervisor classifier (a deliberate decision recorded in `docs/deepagent/architecture_review_report.md`: it keeps TTFT low by avoiding an extra LLM routing call).

## Tool factory set

All factories live in `backend/app/agent/subagents/sql/tools.py` and are re-exported through `backend/app/agent/tools/__init__.py`:

| Factory | LLM-visible tool | Behavior |
|---|---|---|
| `create_wrapped_query_tool` | `sql_db_query` | Skill-gated + linter-gated query execution (details in [tools-and-sql-linter](tools-and-sql-linter.md)) |
| `create_sql_example_search_tool` | `search_saved_correct_tool_uses` | Retrieves golden SQL examples from the business retriever (`doc_type="sql_example"`, domain-scoped by `required_skill`) |
| `create_db_value_lexicon_tool` | `search_db_value_lexicon` | Column-value dedup lexicon lookup for correction |
| `create_db_row_lexicon_tool` | `search_db_row_lexicon` | Row-level lexicon lookup |
| `create_db_table_schema_tool` | `search_db_table_schema` | DDL skeleton lookup |

Lexicon tools return `"Error: Database lexicon retriever is not initialized or disabled."` when the retriever is absent — the same `Error: ` prefix contract that makes [PromptCompilerMiddleware](middleware-pipeline.md) failure-collapse work.

## Guarded query pipeline

`create_wrapped_query_tool` wraps the stock `sql_db_query` tool and enforces, in order (full details in [tools-and-sql-linter](tools-and-sql-linter.md)):

1. **Skill gate** — `required_skill` must be in `runtime.state["skills_loaded"]` (populated by `load_skill` through `SqlSubAgentState`, see [state-and-context](state-and-context.md)).
2. **SQL Linter** — `validate_readonly_query` when `settings.sql_linter_enabled` (see `backend/app/agent/utils/sql_linter.py`).
3. **Checker mode** — optional `sql_db_query_checker` run when `settings.sql_checker_mode == "safety"`.
4. **Execute + normalize** — ISO-8601 date cleaning, Decimal→float, then hard row-limit truncation (`sql_result_hard_limit` / `dimension_result_hard_limit`) with a preview + self-heal guidance block.
5. **Side channel** — returns `Command(update={"messages": [ToolMessage], "tool_artifact": {...query_result...}})` so the full result set reaches the UI without occupying LLM context (see [artifact-lifecycle](../workflows/artifact-lifecycle.md)).

## System prompt

- `base_system_prompt.md` (the SQL expert prompt, `settings.system_prompt_path` default) + `prompts.py::_build_system_prompt(db)` which renders table-structure context.
- The subagent's prompt is what `SkillMiddleware` / `PromptCompilerMiddleware` compile per model call (see [middleware-pipeline](middleware-pipeline.md)).

## Invariants & tests

- Subagent owns `SkillMiddleware` + `PromptCompilerMiddleware` exclusively — `backend/tests/agent/test_agent_component_boundaries.py`.
- Lexicon tool behavior — `backend/tests/agent/tools/test_sql_lexicon_tools.py` (`test_db_value_lexicon_tool`, `test_db_row_lexicon_tool`, `test_db_table_schema_tool`).
- Chart/CSV tools must work under both `CustomState` (main) and `SqlSubAgentState` (subagent) — `backend/tests/agent/test_tools_main_and_subagent_compatibility.py`.

## Change recipe: add a new tool to the SQL subagent

1. Define the tool in `backend/app/agent/subagents/sql/tools.py` using the `ToolRuntime[RequestContext, SqlSubAgentState]` native signature convention (see [tools-and-sql-linter](tools-and-sql-linter.md) — a `| None = None` union on the runtime param breaks Pydantic JSON-schema generation).
2. Re-export from `backend/app/agent/tools/__init__.py` (`__all__` + import), then register in `_prepare_tools` in `backend/app/agent/service.py`.
3. Expected errors: `raise ToolException("Error: ...")` with `handle_tool_error = True`, so `PromptCompilerMiddleware` can fold the failed call (contract in `AGENTS.md`).
4. If the tool produces user-facing data, return a `Command(update={... "tool_artifact": ...})` and add the payload kind to [artifact-lifecycle](../workflows/artifact-lifecycle.md) concerns.
5. Validate: `cd backend && python -m pytest tests/agent/test_tools_main_and_subagent_compatibility.py tests/agent/tools -q`.
