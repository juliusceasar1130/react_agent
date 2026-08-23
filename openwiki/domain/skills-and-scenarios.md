---
type: 领域
title: "技能与场景（领域知识层）"
description: "通过目录约定驱动发现领域技能与场景技能，并管理其注册表/重载；同时提供无需 LLM 的直接路径场景引擎，可在毫秒内处理固定查询。"
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

# 技能与场景

`backend/app/skills/` 是 [SQL 子代理](../architecture/subagent-sql.md) 按需加载的领域知识层。它使用目录约定发现来替代手工维护的提示词块。编写约定位于 `docs/skills/`（权威文档：`docs/skills/scenario_architecture_spec.md`）。

## 发现与注册表

| 符号 | 文件 | 作用 |
|---|---|---|
| `discover_domains` | `backend/app/skills/discovery.py` | 扫描 `backend/app/skills/domains/`；每个领域目录必须包含 `meta.py` + `domain.md`（缺少 `domain.md` 时抛出异常；缺少 `meta.py` 时跳过） |
| `discover_scenarios` | `backend/app/skills/discovery.py` | 扫描 `domains/<domain>/scenarios/` 子目录 |
| `reload_skills` | `backend/app/skills/registry.py` | 重新运行发现流程，并原子化替换模块级 `_RegistryState`；在导入时及通过 `POST /api/chat/skills/reload` 调用 |
| `get_all_skills` / `get_domain_skills` | `backend/app/skills/registry.py` | 为 [SkillMiddleware](../architecture/middleware-pipeline.md) 的提示词注入以及仪表盘/场景端点提供数据 |
| `load_skill`, `load_scenario` | `backend/app/agent/tools/skill_tools.py` | 由 `SkillMiddleware` 注册的 LLM 可见工具；更新 `SqlSubAgentState`（`skills_loaded`、`active_skill`、`scenarios_loaded`） |

当前发现的领域（目录证据，`backend/app/skills/domains/`）：`paint_shop_defect_analysis` 和 `paint_shop_vehicle_logistics`。

## 直接路径场景引擎（无需 LLM）

`backend/app/skills/direct_path/` 是一个纯函数流水线——`resolver`（参数）、`executor`（SQL）、`formatter`（输出）——针对固定统计场景完全绕过 LLM：

- 当 `direct_path_enabled` 已设置，或该场景具有 `sql_template_refs` + `default_template` 时，`is_direct_path_enabled`（位于 `backend/app/routers/scenarios.py`）会将场景标记为直接路径。
- 由 `backend/app/routers/scenarios.py` 提供：`GET /api/scenarios`（树形结构）、`GET /{domain}/{scenario}/params`、`POST /{domain}/{scenario}/execute`（带 LIMIT/OFFSET 分页和真实 `COUNT(*)` 的同步安全执行）。
- 前端界面：`FloatingScenarioCards.vue` / `ScenarioModal.vue`（参见 [chat-app](../frontend/chat-app.md)）。

`GET /api/chat/skills` 仪表盘发现（前端 `WelcomeDashboard.vue` / `stores/skills.ts`）由同一注册表驱动。

## 不变量与测试

- 场景 API + 引擎行为：`backend/tests/test_scenario_quick_panel_api.py`（`test_scenario_schemas_validation`、`test_api_list_scenarios`、`test_api_execute_scenario_invalid_name`）和 `backend/tests/test_scenario_quick_panel_engine.py`（`test_infer_widget`、`test_build_executed_sql_with_valid_and_empty_params`、`test_format_result_table`、`test_stranded_vehicle_scenario_metadata`）。
- 路由级技能端点：`backend/tests/test_routers_coverage.py::test_skills_router_get`、`test_skills_router_reload`。

## 变更指南：添加新的领域技能

1. 创建 `backend/app/skills/domains/<domain_name>/`，其中包含 `meta.py`、`domain.md` 以及可选的 `scenarios/` 目录树（每个场景目录包含其 meta 与 SQL 模板）。
2. 必须存在 `domain.md`（若缺失，发现流程会抛出异常）；`meta.py` 提供 `title`/`description`/`tags`。
3. 无需代码变更——`reload_skills()`（或 `POST /api/chat/skills/reload`）即可加载它；Docker 将 `./backend/app/skills/domains` 挂载为卷，因此技能内容无需重新构建镜像即可发布（参见 `docker-compose.yml`）。
4. 验证：运行场景测试以及 `test_skills_router_get`。