---
type: 领域
title: "技能与场景（领域知识层）"
description: "通过目录约定驱动发现领域技能与场景技能，并管理其注册表/重载；同时提供无需 LLM 的直接路径场景引擎（固定查询毫秒级响应），以及配套前端直通面板契约：executeScenarioApi 单独 60s 超时 + 独立竞态守卫。"
tags: [domain, skills, scenarios, direct-path]
openwiki:
  roles: [domain]
  change_kinds: [content, tooling]
  source_paths: [backend/app/skills/discovery.py, backend/app/skills/registry.py, backend/app/skills/models.py, backend/app/skills/direct_path/resolver.py, backend/app/skills/direct_path/executor.py, backend/app/skills/direct_path/formatter.py, backend/app/routers/scenarios.py, frontend/src/api/scenarios.ts, frontend/src/stores/scenarioPanel.ts, frontend/src/components/chat/VariantB.vue]
  symbols: [discover_domains, discover_scenarios, reload_skills, get_domain_skills, resolve_params, execute_scenario, format_result, build_executed_sql, executeScenarioApi, useScenarioPanelStore, fetchTableData]
  test_paths: [backend/tests/test_scenario_quick_panel_api.py, backend/tests/test_scenario_quick_panel_engine.py]
  invariants:
    - A domain directory must contain both meta.py and domain.md or discovery skips/fails it.
    - Direct-path scenarios are identified by an explicit direct_path_enabled flag or by having sql_template_refs plus a default_template.
    - 前端契约与后端 executor 条件绑定修复互为补充：executeScenarioApi 单独 60s 超时（全局 axios 实例 10s），scenarioPanel 的 paramsGuard/queryGuard 与 VariantB 的 tableDataGuard 均独立防竞态。
  validation_commands: ["cd backend && python -m pytest tests/test_scenario_quick_panel_api.py tests/test_scenario_quick_panel_engine.py -q", "cd frontend && npx vue-tsc --noEmit"]
verified:
  - by: openwiki/0.4.3
    at: 2026-08-30T11:05:45.248Z
sources:
  - id: openwiki-source-fe4544fa9904770d2056d14c
    resource: repo://backend/app/agent/state.py
  - id: openwiki-source-3c31ce63216574dc7def4ebe
    resource: repo://backend/app/agent/tools/skill_tools.py
  - id: openwiki-source-6f941dab5b050be705ad11a9
    resource: repo://backend/app/routers/scenarios.py
  - id: openwiki-source-9826e6420ae7faff47ecd619
    resource: repo://backend/app/skills/direct_path/executor.py
  - id: openwiki-source-7a81c36930f4237dc5ce1939
    resource: repo://backend/app/skills/direct_path/formatter.py
  - id: openwiki-source-79bc724a96ed501000535882
    resource: repo://backend/app/skills/direct_path/resolver.py
  - id: openwiki-source-64e7dcb284a9a937f441114a
    resource: repo://backend/app/skills/discovery.py
  - id: openwiki-source-d50b08f254da625c2ccba324
    resource: repo://backend/app/skills/domains/paint_shop_vehicle_logistics/scenarios/stranded_vehicle_detection/scenario.py
  - id: openwiki-source-4d343ac3ea9002a6684fe937
    resource: repo://backend/app/skills/registry.py
  - id: openwiki-source-25c4c298675256439df22c65
    resource: repo://backend/tests/test_routers_coverage.py
  - id: openwiki-source-755bb03dd8dca927b694125f
    resource: repo://backend/tests/test_scenario_quick_panel_api.py
  - id: openwiki-source-79d2019b4c81dba738b579c7
    resource: repo://backend/tests/test_scenario_quick_panel_engine.py
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-4a11add55cd5e054f02cd8e1
    resource: repo://frontend/src/api/index.ts
  - id: openwiki-source-9a72558f6c9f2ceb85849667
    resource: repo://frontend/src/api/scenarios.ts
  - id: openwiki-source-95742518b33545ac3bf0685f
    resource: repo://frontend/src/components/chat/VariantB.vue
  - id: openwiki-source-f165cf3dc70459a1ba9e2330
    resource: repo://frontend/src/stores/scenarioPanel.ts
generated: { by: "openwiki/0.4.3", at: "2026-08-30T11:05:45.248Z" }
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
- 由 `backend/app/routers/scenarios.py` 提供：`GET /api/scenarios`（树形结构，仅列出直通开启的场景）、`GET /{domain}/{scenario}/params`、`POST /{domain}/{scenario}/execute`（带 LIMIT/OFFSET 分页和真实 `COUNT(*)` 的同步安全执行）。
- 前端界面：`FloatingScenarioCards.vue` / `ScenarioModal.vue`（参见 [chat-app](../frontend/chat-app.md)）。

`GET /api/chat/skills` 仪表盘发现（前端 `WelcomeDashboard.vue` / `stores/skills.ts`）由同一注册表驱动。

### 前端直通面板契约（与后端引擎互为补充）

直通面板的请求侧契约位于 `frontend/src/api/scenarios.ts` 与 `frontend/src/stores/scenarioPanel.ts`，与后端 `executor.py` 的条件绑定修复（回归测试 `test_build_executed_sql_fragment_without_placeholder_not_bound`，见下节）互为补充：

- **超时分层**：全局 axios 实例（`frontend/src/api/index.ts`）`timeout: 10000`；`executeScenarioApi` 为真实 SQL 执行单独传 `timeout: 60000`，避免慢查询被全局 10s 超时整单中断；`getScenariosApi` / `getScenarioParamsApi` 等列表/参数类 API 保持 10s 快速失败。
- **store 竞态防护**：`scenarioPanel` store 为 `loadScenarioParams` / `executeQuery` 各设独立 `useRequestGuard`（`paramsGuard` / `queryGuard`，与领域树 `fetchGuard` 隔离）；响应赋值、错误落定、loading 收尾全部经 `isFresh(requestId)` 守卫，快速切场景/翻页时过期响应整体跳过。
- **抽屉双守卫**：`VariantB.vue` 的 Bento 数据字典抽屉 `fetchTableData` 用请求序号（`tableDataGuard.next()` / `isFresh`）+ `activeTable` 目标表比对双重守卫，快速切换抽屉时旧表数据不覆盖新表。

竞态防护模式的完整说明见 [前端流式生命周期](../frontend/streaming-lifecycle.md)。

## 不变量与测试

- 场景 API + 引擎行为：`backend/tests/test_scenario_quick_panel_api.py`（`test_scenario_schemas_validation`、`test_api_list_scenarios`、`test_api_get_scenario_params`、`test_api_execute_scenario_invalid_name`）和 `backend/tests/test_scenario_quick_panel_engine.py`（`test_infer_widget`、`test_build_executed_sql_with_valid_and_empty_params`、`test_build_executed_sql_fragment_without_placeholder_not_bound`、`test_format_result_table`、`test_stranded_vehicle_scenario_metadata`）。
  - `test_build_executed_sql_fragment_without_placeholder_not_bound` 是 2026-08-30 executor 条件绑定修复的回归：`sql_fragment` 替换后不含 `:param` 占位符（如固定开关片段 `has_defect_only_filter`）时不写入 `bind_vars`，避免 psycopg `Unconsumed named parameter` 500。
- 路由级技能端点：`backend/tests/test_routers_coverage.py::test_skills_router_get`、`test_skills_router_reload`。

## 变更指南：添加新的领域技能

1. 创建 `backend/app/skills/domains/<domain_name>/`，其中包含 `meta.py`、`domain.md` 以及可选的 `scenarios/` 目录树（每个场景目录包含其 meta 与 SQL 模板）。
2. 必须存在 `domain.md`（若缺失，发现流程会抛出异常）；`meta.py` 提供 `title`/`description`/`tags`。
3. 无需代码变更——`reload_skills()`（或 `POST /api/chat/skills/reload`）即可加载它；Docker 将 `./backend/app/skills/domains` 挂载为卷，因此技能内容无需重新构建镜像即可发布（参见 `docker-compose.yml`）。
4. 验证：运行场景测试以及 `test_skills_router_get`。
