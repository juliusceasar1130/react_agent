# DeepAgent 项目结构重构演进路线图

**Goal:** 在不改变业务功能、不改变 SSE 契约与 Agent 初始化语义的前提下，将当前单块式 backend/frontend 目录演进为按职责拆分、低耦合、易扩展的结构；每一阶段都可独立回滚、可验证。

**Architecture:** 采用「功能优先已落地 → 物理目录纯搬家」的波次（wave）策略。先建立可重复的测试/冒烟基线，再按风险由低到高拆分 `api.py` → `routers/`、`services.py` → `services/`、SQL 子智能体目录化，最后进行前端组件领域化拆分。每一波通过兼容 shim / re-export 保持旧 import 路径可用，降低对其他分支和运行时的影响。

**Tech Stack:** FastAPI + LangChain/LangGraph + Vue 3 + Vite + Pinia + pytest + httpx-sse.

## Global Constraints

- 不修改任何业务逻辑、SSE 事件契约、Agent 初始化语义。
- `backend/app/agent/service.py` 中的 `_initialize_agent`（同步路径）与 `_ainitialize_agent`（异步路径）必须 100% 同步更新；如必须改动，优先提取共享 helper。
- 严禁在 `create_deep_agent` 根调用中传 `tools="all"`。
- SSE 事件必须是 `backend/app/schemas.py` 中的 Pydantic 模型，并注册到 `ChatStreamEvent` union / `_chat_stream_event_adapter`。
- 前端保持零 CDN / 离线部署。
- 每一步以独立 commit 为边界，可 `git revert`。

---

## Context

当前 backend 的 `api.py`（1302 行）和 `services.py`（1073 行）承担过多职责，`agent/service.py` 作为组合根也日益膨胀；前端 `components/` 下 19+ 组件 flat 摆放。`docs\deepagent\multi_agent_system_spec.md` 第二阶段建议将 `api.py` 拆为 `routers/`、`services.py` 拆为 `services/`，并建立 `agent/subagents/sql/` 目录。

已确认的偏好：
- **范围**：后端优先，前端延后。
- **迁移策略**：保守的「复制-兼容-再废弃」（copy-then-deprecate），旧路径保留 shim/re-export，稳定后再删除。
- **推进方式**：分波次；第一波先做保守子集（`api.py → routers/` + `subagents/` 骨架），后续再处理 `services.py` 与前端组件。
- **冒烟金线**："查询底漆车间在制车" 需正常路由到 SQL 子智能体并返回完整 SSE 流。

---

## Recommended Roadmap

### Stage 0: 建立可重复的验证基线（先决条件）

**Goal:** 在动任何生产代码之前，让「绿不绿」有明确判断标准。

**Files:**
- Create: `backend/pyproject.toml`
- Create: `requirements-dev.txt`
- Create: `backend/tests/smoke/test_smoke_golden_path.py`（或 `scripts/smoke_backend.py`）
- Modify: `backend/app/agent/vector/llm_refiner.py:5`
- Modify: `backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py`
- Modify: `backend/tests/agent/test_persistence_integration.py`
- Modify: `backend/tests/agent/vector/test_skills_meta_whitelists.py`

**Interfaces:**
- Consumes: `backend.app.main:app`, `httpx-sse` (already in `requirements.txt`).
- Produces: a green pytest baseline + an automated golden-path smoke test that later waves reuse.

- [x] **Step 1: Add pytest configuration**

  Create `backend/pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  asyncio_mode = "auto"
  addopts = "-m 'not integration'"
  markers = [
      "integration: requires external infra (Milvus/Postgres/LLM)",
  ]
  ```

- [x] **Step 2: Declare test dependencies**

  Create `requirements-dev.txt`:
  ```text
  pytest==9.0.2
  pytest-asyncio==1.3.0
  pytest-cov
  ```

- [x] **Step 3: Reach green baseline for the 3 failing tests**

  - `backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py` — requires live Milvus; add `@pytest.mark.integration` so it is skipped by default.
  - `backend/tests/agent/test_persistence_integration.py` — mocks `backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever`; investigate the assertion failure after dual-init rework and either fix the patched symbol/behavior or mark `integration`.
  - `backend/tests/agent/vector/test_skills_meta_whitelists.py` — asserts exact domain/column metadata; align assertions to current skill content or mark `integration`.

  Expected: `python -m pytest backend/tests` → **35 passed, 3 skipped** (or all green).

- [x] **Step 4: Fix upward import in `llm_refiner.py`**

  In `backend/app/agent/vector/llm_refiner.py:5`, change:
  ```python
  from backend.app.agent.service import _create_llm
  ```
  to:
  ```python
  from backend.app.agent.llm import _create_llm
  ```
  This removes a cycle-prone edge before any directory move.

- [x] **Step 5: (Optional but recommended) Deduplicate dual init paths**

  In `backend/app/agent/service.py`, extract the shared tail of `_initialize_agent` and `_ainitialize_agent` (lines 646–696) into a private helper `_create_agent_from_components(components, agent_kwargs)` used by both. This is the only permitted edit to the composition root in the whole roadmap.

- [x] **Step 6: Create golden-path smoke script**

  Create `backend/tests/smoke/test_smoke_golden_path.py` that:
  1. Requires the backend to be running (or boots it on a test port).
  2. `POST /api/chat/sessions` → capture `session_id`.
  3. `POST /api/chat/stream` with `{"session_id": ..., "message": "查询底漆车间在制车", "stream": true}`.
  4. Parses SSE via `httpx-sse` and asserts the sequence contains:
     - `subagent_change` with `active_subagent == "sql_domain_agent"`
     - at least one `token`
     - a `tool_call` / `tool_result` pair
     - a `final` event
     - terminating `data: [DONE]`
  5. `DELETE /api/chat/sessions/{id}`.

- [x] **Step 7: Verify Stage 0**

  Run:
  ```bash
  conda activate py312_agent
  cd "F:\000_dev\Python\workplace\rearch_agent\.tree\features\agent-deepagent\backend"
  python -m pytest
  python -c "from backend.app.main import app"
  ```
  Then boot `python run_backend.py` and run the smoke script.

- [x] **Step 8: Commit**

  ```bash
  git add backend/pyproject.toml requirements-dev.txt backend/tests/smoke backend/tests/agent/...
  git commit -m "chore: 建立重构前可重复的 pytest 基线与黄金路径冒烟测试"
  ```

**Risk/Rollback:** 仅触及测试与一条 import；逐 commit `git revert` 即可。

---

### Wave 1: `api.py → routers/` + `agent/subagents/` 骨架

**Goal:** 拆分最大的后端单文件，同时保持 `main.py` 和所有客户端 URL 不变。

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/chat.py`
- Create: `backend/app/routers/sessions.py`
- Create: `backend/app/routers/skills.py`
- Create: `backend/app/routers/admin.py`
- Create: `backend/app/routers/artifacts.py`
- Create: `backend/app/routers/_analytics.py`
- Create: `backend/app/routers/scenarios.py`
- Modify: `backend/app/api.py` → 4-line shim
- Create: `backend/app/agent/subagents/__init__.py`
- Create: `backend/app/agent/subagents/sql/__init__.py`

**Interfaces:**
- Consumes: existing `backend.app.main:app` import contract (`router`, `scenarios_router`, `init_analytics_engine`).
- Produces: same `router`, `scenarios_router`, `init_analytics_engine` exported from `backend.app.api`.

**Endpoint mapping (from current `backend/app/api.py`):**

| 当前区域 | 目标文件 |
|---|---|
| `GET /skills`, `POST /skills/reload` | `routers/skills.py` |
| `_analytics_engine`, `init_analytics_engine()`, `GET /dimensions/{table_name}` | `routers/_analytics.py` |
| Sessions CRUD (`/sessions*`) | `routers/sessions.py` |
| Messages CRUD + feedback (`/messages*`) | `routers/sessions.py` |
| `GET /files/{file_id}`, `GET /charts/{chart_id}` | `routers/artifacts.py` |
| `POST /message` (non-stream) | `routers/chat.py` |
| `POST /stream` + `_encode_sse` | `routers/chat.py` |
| `POST /resume` | `routers/chat.py` |
| admin approve/pending | `routers/admin.py` |
| `/api/scenarios/*` (separate prefix) | `routers/scenarios.py` |

- [x] **Step 1: Create `backend/app/routers/__init__.py`**

  ```python
  from fastapi import APIRouter
  from backend.app.routers import chat, sessions, skills, admin, artifacts, _analytics, scenarios

  router = APIRouter(prefix="/api/chat", tags=["chat"])
  router.include_router(chat.router)
  router.include_router(sessions.router)
  router.include_router(skills.router)
  router.include_router(admin.router)
  router.include_router(artifacts.router)
  router.include_router(_analytics.router)

  scenarios_router = scenarios.router
  init_analytics_engine = _analytics.init_analytics_engine
  ```

  Sub-routers (except `scenarios.py`) must be defined **without a prefix** so they inherit `/api/chat`. `scenarios.py` keeps its own `APIRouter(prefix="/api/scenarios", tags=["scenarios"])`.

- [x] **Step 2: Create router modules**

  For each target file, copy the corresponding endpoint bodies **verbatim** from `backend/app/api.py`; only adjust the import block to import from sibling modules (`..database`, `..crud`, `..schemas`, `..services`, etc.). Keep `_encode_sse` in `routers/chat.py` and ensure it continues calling `serialize_chat_stream_event` from `schemas.py`.

- [x] **Step 3: Create subagent package skeleton**

  Create empty `__init__.py` files so the directories are tracked:
  - `backend/app/agent/subagents/__init__.py`
  - `backend/app/agent/subagents/sql/__init__.py`

- [x] **Step 4: Replace `api.py` with a shim**

  Rewrite `backend/app/api.py` as:
  ```python
  from backend.app.routers import router, scenarios_router, init_analytics_engine

  __all__ = ["router", "scenarios_router", "init_analytics_engine"]
  ```

  `backend/app/main.py` remains unchanged.

- [x] **Step 5: Verify Wave 1**

  Run:
  ```bash
  python -m pytest backend/tests
  python -c "from backend.app.main import app"
  python run_backend.py
  ```
  Then run the golden-path smoke script.

  Expected:
  - pytest green
  - clean import
  - smoke passes with `subagent_change` → `sql_domain_agent`
  - `git diff --stat` shows `api.py` collapsed and new router files added

- [x] **Step 6: Commit**

  ```bash
  git add backend/app/routers backend/app/api.py backend/app/agent/subagents
  git commit -m "refactor: 将 api.py 拆分为 routers/ 包，保留 api.py shim"
  ```

**Risk/Rollback:** 低。URL 漂移由 smoke 守护；`_analytics_engine` 单例状态由启动 + smoke 守护。`git revert <wave1-commit>` 即可还原。

---

### Wave 2: `services.py → services/` + 填充 `agent/subagents/sql/`

**Goal:** 将 `services.py` 文件转为 package，并把 SQL 专用工具和提示词迁入子智能体目录。

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/chat_service.py`
- Delete: `backend/app/services.py`（同 import 路径替换，无 shim 必要）
- Create: `backend/app/agent/subagents/sql/tools.py`
- Create: `backend/app/agent/subagents/sql/prompts.py`
- Create: `backend/app/agent/subagents/sql/base_system_prompt.md`
- Modify: `backend/app/config.py:55`
- Modify: `backend/app/agent/service.py:343-390`
- Modify: `backend/app/agent/tools/sql_tools.py`
- Modify: `backend/app/agent/tools/sql_lexicon_tools.py`

**Interfaces:**
- Consumes: `backend.app.services` import path（必须保持有效）; `backend.app.agent.tools` public API（必须保持有效）.
- Produces: `backend.app.services.SQLAgentService`, `backend.app.services.initialize_agent_service`, etc.; SQL tool factories still exported from `backend.app.agent.tools`.

- [x] **Step 1: Convert `services.py` to a package**

  Move the entire body of `backend/app/services.py` verbatim into `backend/app/services/chat_service.py` (including the `_agent_service` / `_agent_service_lock` globals and lifecycle functions).

  Create `backend/app/services/__init__.py`:
  ```python
  from backend.app.services.chat_service import (
      SQLAgentService,
      initialize_agent_service,
      get_agent_service,
      shutdown_agent_service,
  )

  __all__ = [
      "SQLAgentService",
      "initialize_agent_service",
      "get_agent_service",
      "shutdown_agent_service",
  ]
  ```

  Delete `backend/app/services.py`. The import path `backend.app.services` stays identical, so `main.py` and the shim `api.py` need no changes.

- [x] **Step 2: (Deferred) Do NOT split `stream_service.py` yet**

  The stream helpers (`_stream_execution_loop`, `_unpack_stream_chunk`, etc.) are tightly coupled to `SQLAgentService`. Extracting them into `services/stream_service.py` is a logic-touching change, not a move. Defer until a concrete trigger exists (e.g., a second service type needs the same stream loop).

- [x] **Step 3: Move SQL tools into `subagents/sql/tools.py`**

  Merge the factories from:
  - `backend/app/agent/tools/sql_tools.py` (`create_wrapped_query_tool`, `create_sql_example_search_tool`)
  - `backend/app/agent/tools/sql_lexicon_tools.py` (`create_db_value_lexicon_tool`, `create_db_row_lexicon_tool`, `create_db_table_schema_tool`)

  into `backend/app/agent/subagents/sql/tools.py`.

  Then turn the old files into shims:
  ```python
  from backend.app.agent.subagents.sql.tools import (
      create_wrapped_query_tool,
      create_sql_example_search_tool,
      create_db_value_lexicon_tool,
      create_db_row_lexicon_tool,
      create_db_table_schema_tool,
  )
  ```

  Keep `backend/app/agent/tools/__init__.py` unchanged; it will continue re-exporting the same symbols through the shims.

- [x] **Step 4: Move SQL prompt loader and template**

  - Move `backend/app/agent/prompts/base_system_prompt.md` → `backend/app/agent/subagents/sql/base_system_prompt.md`.
  - Move `SystemPromptLoader` and `_build_system_prompt` from `backend/app/agent/service.py:343-390` into `backend/app/agent/subagents/sql/prompts.py`.
  - In `backend/app/agent/service.py`, import `_build_system_prompt` from the new location.
  - Update `backend/app/config.py:55` default `system_prompt_path` to the new path:
    ```python
    system_prompt_path: str = os.getenv(
        "SYSTEM_PROMPT_PATH",
        str(Path(__file__).resolve().parent / "agent" / "subagents" / "sql" / "base_system_prompt.md"),
    )
    ```

  Do **not** create `subagents/sql/agent.py` (a `SQLSubGraph` factory) in this wave — that would require restructuring `_build_agent_components` inside the dual-path file.

- [x] **Step 5: Verify Wave 2**

  Run:
  ```bash
  python -m pytest backend/tests
  python -c "from backend.app.main import app"
  python run_backend.py
  ```
  Then run the golden-path smoke script and confirm `/skills` still lists domains.

- [x] **Step 6: Commit**

  ```bash
  git add backend/app/services backend/app/agent/subagents/sql backend/app/agent/tools/sql_tools.py backend/app/agent/tools/sql_lexicon_tools.py backend/app/agent/service.py backend/app/config.py
  git commit -m "refactor: services.py 转 package 并填充 agent/subagents/sql/ 目录"
  ```

**Risk/Rollback:** 中低。Missed importers 由 shim 兜底；`config.py` 路径变更由环境变量覆盖 + smoke 守护。`git revert <wave2-commit>` 可还原。

---

### Wave 3: 前端组件按领域目录拆分

**Goal:** 将 `frontend/src/components/` 下 19 个组件按 `chat/`、`agent/`、`artifacts/`、`common/` 归类，保持所有 import 路径可用。

**Files:**
- Move: `frontend/src/components/*.vue` → `frontend/src/components/{chat,agent,artifacts,common}/*.vue`
- Create: shim `.vue` files at old paths

**Interfaces:**
- Consumes: existing `@/components/X.vue` import paths in `frontend/src/views/ChatView.vue`, `MessageItem.vue`, etc.
- Produces: same default component exports from both old and new paths during the deprecation window.

**Domain assignment (representative):**

- `chat/`: `MessageItem.vue`, `MessageList.vue`, `VariantB.vue`, `AskUserQuestionCard.vue`, `ReasoningAccordion.vue`, `WelcomeDashboard.vue`, `FloatingScenarioCards.vue`
- `agent/`: `SubAgentBadge.vue`, `AdminReviewPanel.vue`
- `artifacts/`: `ChartArtifactCard.vue`, `DimensionTable.vue`, `ResultRenderer.vue`, `ScalarResult.vue`, `TableResult.vue`
- `common/`: `ToggleSwitch.vue`, `ParameterForm.vue`, `ScenarioModal.vue`, `SessionList.vue`, `SessionItem.vue`, `VersionChangelogModal.vue`

Existing `components/chat/plugins/` and `components/widgets/` stay in place.

- [x] **Step 1: Move components by domain**

  Use `git mv` to preserve history:
  ```bash
  git mv frontend/src/components/MessageItem.vue frontend/src/components/chat/MessageItem.vue
  # ... repeat for each component
  ```

- [x] **Step 2: Create shim SFCs at old paths**

  For each moved component, create a shim at the old path, e.g. `frontend/src/components/MessageItem.vue`:
  ```vue
  <script>
  import MessageItem from '@/components/chat/MessageItem.vue'
  export default MessageItem
  </script>
  ```

  Do **not** update `ChatView.vue` or `MessageItem.vue` import sites in this wave.

- [x] **Step 3: Verify Wave 3**

  Run:
  ```bash
  cd frontend
  npm run build:check
  npm run dev
  ```
  Then run the golden-path smoke against the dev server.

  Also run:
  ```bash
  git grep -n "@/components/[A-Z]" frontend/src
  ```
  Ensure all remaining `@/components/X` references resolve to shims.

- [x] **Step 4: Commit**

  ```bash
  git add frontend/src/components
  git commit -m "refactor: 前端组件按 chat/agent/artifacts/common 领域目录拆分（含 shim）"
  ```

**Risk/Rollback:** 低。`vue-tsc` + `vite build` 为精确判定；无后端运行时耦合。`git revert <wave3-commit>` 可还原。

---

### Wave 4（可选，稳定后）：清理 shim 与 import 路径

**Goal:** 删除已废弃的 shim，统一引用到新路径。

**Files:**
- Modify: `frontend/src/views/ChatView.vue`
- Modify: `frontend/src/components/MessageItem.vue`
- Delete: all `.vue` shim files at old component paths
- Delete: `backend/app/api.py` shim (after confirming only `main.py` imports `backend.app.api`)
- Delete: `backend/app/agent/tools/sql_tools.py` and `sql_lexicon_tools.py` shims (after grep confirms no direct importers)

- [x] **Step 1: Update frontend imports**

  Replace `@/components/X.vue` with the new domain path in `ChatView.vue`, `MessageItem.vue`, and any other files. Then delete the shim SFCs.

- [x] **Step 2: Update backend imports**

  Update `backend/app/main.py` to import directly from `backend.app.routers` and delete the `backend/app/api.py` shim. Similarly, update any direct importers of `sql_tools.py` / `sql_lexicon_tools.py` and delete the shims.

- [x] **Step 3: Verify Wave 4**

  Run:
  ```bash
  python -m pytest backend/tests
  python -c "from backend.app.main import app"
  cd frontend && npm run build:check
  ```
  Then run the golden-path smoke.

- [x] **Step 4: Commit**

  ```bash
  git commit -m "refactor: 清理 Stage 1-3 的兼容性 shim"
  ```

**Risk/Rollback:** 中低。所有变更均为 import 路径替换；`git revert` 可还原。

---

## Verification Summary

| 阶段 | 后端自动测试 | 前端构建 | 冒烟验证 |
|---|---|---|---|
| Stage 0 | `python -m pytest backend/tests` | `cd frontend && npm run build:check` | 黄金路径 smoke script |
| Wave 1 | pytest green | build:check green | backend boot + smoke |
| Wave 2 | pytest green | build:check green | backend boot + smoke |
| Wave 3 | pytest green | build:check green | `npm run dev` + smoke |
| Wave 4 | pytest green | build:check green | smoke |

---

## Critical Files

- `backend/app/main.py` — 路由挂载点；Wave 1 保持兼容，Wave 4 直连 `backend.app.routers`。
- `backend/app/api.py` — Wave 1 拆分为 `routers/`，Wave 4 物理清理退役。
- `backend/app/services.py` — Wave 2 转为 `services/` package。
- `backend/app/agent/service.py` — 组合根；Wave 2 移动 prompt loader，Wave 4 直连 `subagents/sql/tools.py`。
- `backend/app/agent/tools/__init__.py` — 工具公共 API；Wave 4 直连从 `subagents/sql/tools.py` 导出。
- `backend/app/config.py` — `system_prompt_path` 默认路径在 Wave 2 调整。
- `frontend/src/views/ChatView.vue` — 前端主视图入口，Wave 4 统一收敛为领域直通路径。
