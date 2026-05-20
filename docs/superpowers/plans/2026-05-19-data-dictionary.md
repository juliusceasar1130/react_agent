# Data Dictionary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

> 修改时间: 2026-05-20
> 修改内容: 移除 Mock 降级（连接失败直接报错），白名单改用 .env DIMENSION_TABLES 配置

**Goal:** Build a frontend data dictionary page (Bento grid + slide-over Drawer mode) that displays dimension table data from analytics_db so users can browse basic information and terminology without relying on RAG.

**Final Architecture:** Variant B — Bento grid dashboard in main content area, slide-over frosted-glass Drawer for table detail. Backend `GET /api/chat/dimensions/{table_name}` with whitelist from `.env` `DIMENSION_TABLES`. Double-click cell injection into chat input.

**Tech Stack:** Python (FastAPI, SQLAlchemy), Vue 3 + TypeScript + Tailwind CSS

---

### Task 1: Backend — Add `GET /api/chat/dimensions/{table_name}` endpoint

**Files:**
- Modify: `backend/app/api.py` — add endpoint after existing `/skills` route
- Create: `backend/app/test_dimensions_api.py` — test the endpoint

- [x] **Step 1: Write the failing API tests**

Create `backend/app/test_dimensions_api.py`: covers whitelist rejection (400), all 5 tables return 200.

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/test_dimensions_api.py -v`
Expected: All tests FAIL with 404 (endpoint not yet defined)

- [x] **Step 3: Implement the endpoint in `backend/app/api.py`**

After the `/skills` endpoint, add:

1. Whitelist from `settings.dimension_tables` (populated from `.env` `DIMENSION_TABLES` — `config.py` already provides the `dimension_tables` property)
2. `GET /dimensions/{table_name}` endpoint:
   - Whitelist not configured → 503
   - Whitelist check → 400 if not allowed
   - `ANALYTICS_DATABASE_URL` not configured → 503
   - DB query via `create_engine(analytics_database_url)`, `SELECT * FROM "{table_name}"`
   - Apply `DIMENSION_RESULT_HARD_LIMIT` (default 300)
   - DB connection/query failure → 500 with error detail logged

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/app/test_dimensions_api.py -v`
Expected: All tests PASS

- [x] **Step 5: Commit**

---

### Task 2: Frontend — Create API layer `dimensions.ts`

**Files:**
- Create: `frontend/src/api/dimensions.ts`

- [x] **Step 1: Create `frontend/src/api/dimensions.ts`**

```typescript
export interface DimensionTableData {
  table_name: string
  columns: string[]
  rows: (string | number)[][]
  row_count: number
}

export function getDimensionTableApi(tableName: string): Promise<DimensionTableData>
```

Wraps `api.get(`/api/chat/dimensions/${encodeURIComponent(tableName)}`)`.

- [x] **Step 2: Commit**

---

### Task 3: Frontend — Create `DimensionTable.vue` component

**Files:**
- Create: `frontend/src/components/DimensionTable.vue`

- [x] **Step 1: Create `frontend/src/components/DimensionTable.vue`**

Props: `title`, `tableName`, `columns`, `rows`

Features:
- HTML table with header and body
- **Copy buttons**: copy table name, copy column name (per header), copy cell value (hover reveal per row)
- **Copy toast**: fixed-position mini toast with fade transition
- **Double-click emit**: `@dblclick-cell` on both header cells and body cells
- **NULL handling**: displays `NULL` text for null/undefined values
- `font-mono text-xs` for data cells, Tailwind hover states

- [x] **Step 2: Commit**

---

### Task 4: Frontend — Create `VariantB.vue` (Bento Grid + Drawer container)

**Files:**
- Create: `frontend/src/components/VariantB.vue`

- [x] **Step 1: Create `frontend/src/components/VariantB.vue`**

Architecture:
- **Sidebar** (left, fixed on mobile): RESEARCH branding header, session list slot
- **Main area** (right): chat slot by default; toggle to Bento grid via floating button
- **Floating toggle button**: "📚 数据字典看板" / "返回对话" pill button at top-right
- **Bento grid**: 5 cards in `md:grid-cols-3` layout with emoji icons, category badges, descriptions, hover lift effect
- **Slide-over Drawer**: right-side frosted-glass panel with backdrop blur
  - Loads DimensionTable on demand via `getDimensionTableApi()`
  - Loading spinner, error state with retry button
  - Slide transition animation
  - Passes `dblclick-cell` event upward to parent

Slots: `sidebar-header-action`, `sidebar-chat-list`, `main-chat-area`
Emits: `closeSidebar`, `dblclick-cell`

- [x] **Step 2: Commit**

---

### Task 5: Frontend — Refactor `ChatView.vue` to use VariantB with double-click injection

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [x] **Step 1: Replace inline sidebar/chat layout with VariantB slots**

Remove old `<aside>` + `<main>` inline layout. Replace with `<VariantB>` using slots.

- [x] **Step 2: Add double-click cell injection logic**

`handleDblClickCell(value)` inserts at cursor position, triggers `.input-glow` animation (1s) and frosted-glass Toast (1.8s).

- [x] **Step 3: Add glow CSS animation and Toast transition**

- [x] **Step 4: Verify TypeScript compilation**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 0 errors (Exit code 0)

- [x] **Step 5: Commit**

---

### Task 6: Cleanup — Remove prototype artifacts

**Files:**
- Delete: `frontend/src/components/VariantA.vue`
- Delete: `frontend/src/components/VariantC.vue`
- Delete: `frontend/src/components/PrototypeSwitcher.vue`

- [x] **Step 1: Physical deletion + clean parent references + verify TS compilation**

- [x] **Step 2: Commit**

---

### Task 7: Documentation — Update README, changelog, memory.md

**Files:**
- Modify: `README.md`, `changelog.md`, `memory.md`

- [x] **Step 1: Add data dictionary entries to changelog.md, README.md, memory.md**

- [x] **Step 2: Commit**

---

### Task 8: Remove Mock fallback, whitelist from .env

**Files:**
- Modify: `backend/app/api.py` — remove `MOCK_DIMENSION_DATA`, use `settings.dimension_tables`, DB failure returns error
- Modify: `frontend/src/api/dimensions.ts` — remove `source` field
- Modify: `frontend/src/components/DimensionTable.vue` — remove `source` prop, badge, warning banner
- Modify: `frontend/src/components/VariantB.vue` — remove `:source` binding
- Modify: `backend/app/test_dimensions_api.py` — remove `source` assertion
- Modify: `docs/superpowers/specs/2026-05-19-data-dictionary-design.md` — align with above changes
- Modify: `docs/superpowers/plans/2026-05-19-data-dictionary.md` — add this task

- [x] **Step 1: Edit all files**

- [ ] **Step 2: Manual verification & commit (user will handle)**
