---
type: Domain
title: "Skills & Scenarios (Domain Knowledge Layer)"
description: "Directory-convention-driven discovery of domain skills and scenario skills, their registry/reload, and the LLM-free direct-path scenario engine that serves fixed queries in milliseconds."
tags: [domain, skills, scenarios, direct-path]
openwiki:
  roles: [domain]
  change_kinds: [content, tooling]
  source_paths: [backend/app/skills/discovery.py, backend/app/skills/registry.py, backend/app/skills/models.py, backend/app/skills/direct_path/resolver.py, backend/app/skills/direct_path/executor.py, backend/app/routers/scenarios.py]
  symbols: [discover_domains, discover_scenarios, reload_skills, get_domain_skills, resolve_params, execute_scenario, format_result]
  test_paths: [backend/tests/test_scenario_quick_panel_api.py, backend/tests/test_scenario_quick_panel_engine.py]
  invariants:
    - A domain directory must contain both meta.py and domain.md or discovery skips/fails it.
    - Direct-path scenarios are identified by an explicit direct_path_enabled flag or by having sql_template_refs plus a default_template.
  validation_commands: ["cd backend && python -m pytest tests/test_scenario_quick_panel_api.py tests/test_scenario_quick_panel_engine.py -q"]
---

# Skills & Scenarios

`backend/app/skills/` is the domain-knowledge layer the [SQL subagent](../architecture/subagent-sql.md) loads on demand. It replaces hand-maintained prompt blobs with directory-convention discovery. Authoring conventions live in `docs/skills/` (authoritative: `docs/skills/scenario_architecture_spec.md`).

## Discovery & registry

| Symbol | File | Role |
|---|---|---|
| `discover_domains` | `backend/app/skills/discovery.py` | Scans `backend/app/skills/domains/`; each domain dir must have `meta.py` + `domain.md` (missing `domain.md` raises; missing `meta.py` skips) |
| `discover_scenarios` | `backend/app/skills/discovery.py` | Scans `domains/<domain>/scenarios/` subdirectories |
| `reload_skills` | `backend/app/skills/registry.py` | Re-runs discovery, atomically swaps the module-level `_RegistryState`; called at import and by `POST /api/chat/skills/reload` |
| `get_all_skills` / `get_domain_skills` | `backend/app/skills/registry.py` | Feed [SkillMiddleware](../architecture/middleware-pipeline.md) prompt injection and the dashboard/scenario endpoints |
| `load_skill`, `load_scenario` | `backend/app/agent/tools/skill_tools.py` | LLM-visible tools registered by `SkillMiddleware`; update `SqlSubAgentState` (`skills_loaded`, `active_skill`, `scenarios_loaded`) |

Currently discovered domains (directory evidence, `backend/app/skills/domains/`): `paint_shop_defect_analysis` and `paint_shop_vehicle_logistics`.

## Direct-path scenario engine (LLM-free)

`backend/app/skills/direct_path/` is a pure-function pipeline — `resolver` (params), `executor` (SQL), `formatter` (output) — that bypasses the LLM entirely for fixed statistical scenarios:

- `is_direct_path_enabled` (in `backend/app/routers/scenarios.py`) marks a scenario as direct-path when `direct_path_enabled` is set or when it has `sql_template_refs` + `default_template`.
- Served by `backend/app/routers/scenarios.py`: `GET /api/scenarios` (tree), `GET /{domain}/{scenario}/params`, `POST /{domain}/{scenario}/execute` (synchronous safe execution with LIMIT/OFFSET pagination and real `COUNT(*)`).
- Frontend surfaces: `FloatingScenarioCards.vue` / `ScenarioModal.vue` (see [chat-app](../frontend/chat-app.md)).

The `GET /api/chat/skills` dashboard discovery (frontend `WelcomeDashboard.vue` / `stores/skills.ts`) is driven by the same registry.

## Invariants & tests

- Scenario API + engine behavior: `backend/tests/test_scenario_quick_panel_api.py` (`test_scenario_schemas_validation`, `test_api_list_scenarios`, `test_api_execute_scenario_invalid_name`) and `backend/tests/test_scenario_quick_panel_engine.py` (`test_infer_widget`, `test_build_executed_sql_with_valid_and_empty_params`, `test_format_result_table`, `test_stranded_vehicle_scenario_metadata`).
- Router-level skills endpoints: `backend/tests/test_routers_coverage.py::test_skills_router_get`, `test_skills_router_reload`.

## Change recipe: add a new domain skill

1. Create `backend/app/skills/domains/<domain_name>/` with `meta.py`, `domain.md`, and an optional `scenarios/` tree (each scenario dir with its meta + SQL templates).
2. `domain.md` must exist (discovery raises if it does not); `meta.py` supplies `title`/`description`/`tags`.
3. No code change needed — `reload_skills()` (or `POST /api/chat/skills/reload`) picks it up; Docker mounts `./backend/app/skills/domains` as a volume so skill content can ship without rebuilding the image (see `docker-compose.yml`).
4. Validate: run the scenario tests plus `test_skills_router_get`.
