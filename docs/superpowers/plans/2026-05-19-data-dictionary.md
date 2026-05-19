# Data Dictionary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a frontend data dictionary page (sidebar tab mode) that displays dimension table data from analytics_db so users can browse basic information and terminology without relying on RAG.

**Architecture:** Add a `GET /api/chat/dimensions/{table_name}` backend endpoint with table-name whitelist, querying analytics_db via SQLAlchemy create_engine. Frontend adds a sidebar tab switch in ChatView, a new `dimensions.ts` API module, and a `DimensionTable.vue` component for rendering table data.

**Tech Stack:** Python (FastAPI, SQLAlchemy), Vue 3 + TypeScript + Tailwind CSS

---

### Task 1: Backend — Add `GET /api/chat/dimensions/{table_name}` endpoint

**Files:**
- Modify: `backend/app/api.py` — add endpoint after existing `/skills` route
- Create: `backend/app/test_dimensions_api.py` — test the endpoint

- [ ] **Step 1: Write the failing API tests**

Create `backend/app/test_dimensions_api.py`:

```python
"""Tests for GET /api/chat/dimensions/{table_name}"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_dimensions_whitelisted_table_returns_200():
    resp = client.get("/api/chat/dimensions/process_areas")
    assert resp.status_code == 200
    data = resp.json()
    assert data["table_name"] == "process_areas"
    assert isinstance(data["columns"], list)
    assert isinstance(data["rows"], list)
    assert "row_count" in data


def test_dimensions_non_whitelisted_table_returns_400():
    resp = client.get("/api/chat/dimensions/vehicle_tracking")
    assert resp.status_code == 400
    assert "not in the dimension whitelist" in resp.json()["detail"]


def test_dimensions_all_five_tables():
    for name in [
        "carrier_types", "process_areas", "vehicle_body_types",
        "vehicle_color_codes", "vehicle_platforms",
    ]:
        resp = client.get(f"/api/chat/dimensions/{name}")
        assert resp.status_code == 200, f"{name} failed: {resp.status_code}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/test_dimensions_api.py -v`
Expected: All 3 tests FAIL with 404 (endpoint not yet defined)

- [ ] **Step 3: Implement the endpoint in `backend/app/api.py`**

After the `/skills` endpoint (line ~86), add:

```python
from sqlalchemy import create_engine, text

DIMENSION_TABLE_WHITELIST = frozenset({
    "carrier_types",
    "process_areas",
    "vehicle_body_types",
    "vehicle_color_codes",
    "vehicle_platforms",
})


@router.get("/dimensions/{table_name}")
def get_dimension_table(table_name: str):
    """获取指定维度表全部数据，用于前端数据字典展示。

    修改时间: 2026-05-19
    修改内容:
    - 新增维度表查询端点，支持前端数据字典页面加载表数据
    """
    if table_name not in DIMENSION_TABLE_WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table_name}' is not in the dimension whitelist",
        )

    analytics_url = settings.analytics_database_url.strip()
    if not analytics_url:
        raise HTTPException(
            status_code=503,
            detail="Analytics database is not configured",
        )

    try:
        engine = create_engine(analytics_url)
        with engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM "{table_name}"')
            )
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
            return {
                "table_name": table_name,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
    except Exception as exc:
        logger.error("维度表查询失败 table=%s: %s", table_name, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query dimension table: {exc}",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/app/test_dimensions_api.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api.py backend/app/test_dimensions_api.py
git commit -m "feat: add GET /api/chat/dimensions/{table_name} endpoint"
```

---

### Task 2: Frontend — Create API layer `dimensions.ts`

**Files:**
- Create: `frontend/src/api/dimensions.ts`

- [ ] **Step 1: Create `frontend/src/api/dimensions.ts`**

```typescript
import api from './index'

export interface DimensionTableData {
  table_name: string
  columns: string[]
  rows: string[][]
  row_count: number
}

export function getDimensionTableApi(tableName: string): Promise<DimensionTableData> {
  return api.get(`/api/chat/dimensions/${encodeURIComponent(tableName)}`) as Promise<DimensionTableData>
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/dimensions.ts
git commit -m "feat: add frontend dimensions API module"
```

---

### Task 3: Frontend — Create `DimensionTable.vue` component

**Files:**
- Create: `frontend/src/components/DimensionTable.vue`

- [ ] **Step 1: Create `frontend/src/components/DimensionTable.vue`**

```vue
<template>
  <div class="mx-auto w-full max-w-5xl px-3 py-6 sm:px-5 lg:px-8">
    <div class="mb-5">
      <h2 class="text-xl font-semibold text-text">{{ title }}</h2>
      <p class="mt-1 text-sm text-neutral-500">共 {{ rows.length }} 行</p>
    </div>

    <div v-if="rows.length === 0" class="panel p-8 text-center text-sm text-neutral-500">
      该表暂无数据
    </div>

    <div v-else class="overflow-x-auto rounded-2xl border border-neutral-200/80 bg-white shadow-sm">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-neutral-200 bg-neutral-50/80">
            <th
              v-for="col in columns"
              :key="col"
              class="px-4 py-3 text-left font-medium text-neutral-600 whitespace-nowrap"
            >
              {{ col }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, ri) in rows"
            :key="ri"
            class="border-b border-neutral-100 last:border-0 hover:bg-neutral-50/50 transition-colors"
          >
            <td
              v-for="(cell, ci) in row"
              :key="ci"
              class="px-4 py-2.5 text-neutral-700 whitespace-nowrap"
            >
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  columns: string[]
  rows: string[][]
}>()
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DimensionTable.vue
git commit -m "feat: add DimensionTable component for data dictionary display"
```

---

### Task 4: Frontend — Modify `ChatView.vue` sidebar with tab switching

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: Add tab state, table list, and selection logic to `<script setup>`**

In `<script setup>`, add after `const messageListRef = ref<...>(null)` (around line 189):

```typescript
import { getDimensionTableApi, type DimensionTableData } from '@/api/dimensions'
import DimensionTable from '@/components/DimensionTable.vue'

const TAB_LABELS: Record<string, string> = {
  carrier_types: '载体类型',
  process_areas: '工艺区域',
  vehicle_body_types: '车型字典',
  vehicle_color_codes: '颜色字典',
  vehicle_platforms: '平台字典',
}

const sidebarTab = ref<'chat' | 'dictionary'>('chat')
const selectedDimensionTable = ref<string | null>(null)
const dimensionData = ref<DimensionTableData | null>(null)
const dimensionLoading = ref(false)
const dimensionError = ref<string | null>(null)

const dimensionTableNames = Object.keys(TAB_LABELS)

async function selectDimensionTable(name: string) {
  selectedDimensionTable.value = name
  dimensionLoading.value = true
  dimensionError.value = null
  try {
    dimensionData.value = await getDimensionTableApi(name)
  } catch (e: any) {
    dimensionError.value = e.message || '加载失败'
    dimensionData.value = null
  } finally {
    dimensionLoading.value = false
  }
}
```

- [ ] **Step 2: Replace sidebar content area with tab-conditional rendering**

Replace the sidebar content from `<header>` to `</aside>` (lines 14-50). Keep `<header>` and `<SessionList @selected="closeSidebar" />`, but add tabs and conditional rendering:

After `<header>...</header>` (the sidebar header), replace:

```html
      <div class="border-b border-neutral-200/70 px-4 py-3 text-xs text-neutral-600 sm:px-5">
        在这里管理会话，保持不同话题的上下文更清晰。
      </div>

      <SessionList @selected="closeSidebar" />
```

With:

```html
      <!-- Tab 切换 -->
      <div class="flex border-b border-neutral-200/70">
        <button
          class="flex-1 px-4 py-3 text-sm font-medium transition-colors"
          :class="sidebarTab === 'chat'
            ? 'border-b-2 border-primary text-primary'
            : 'text-neutral-500 hover:text-text'"
          @click="sidebarTab = 'chat'"
        >
          对话
        </button>
        <button
          class="flex-1 px-4 py-3 text-sm font-medium transition-colors"
          :class="sidebarTab === 'dictionary'
            ? 'border-b-2 border-primary text-primary'
            : 'text-neutral-500 hover:text-text'"
          @click="sidebarTab = 'dictionary'"
        >
          数据字典
        </button>
      </div>

      <!-- 对话 Tab 内容 -->
      <template v-if="sidebarTab === 'chat'">
        <div class="border-b border-neutral-200/70 px-4 py-3 text-xs text-neutral-600 sm:px-5">
          在这里管理会话，保持不同话题的上下文更清晰。
        </div>
        <SessionList @selected="closeSidebar" />
      </template>

      <!-- 数据字典 Tab 内容 -->
      <div v-else class="flex-1 overflow-y-auto">
        <div class="border-b border-neutral-200/70 px-4 py-3 text-xs text-neutral-600 sm:px-5">
          选择维度表查看基础信息与术语定义
        </div>
        <nav class="flex flex-col gap-0.5 p-2">
          <button
            v-for="name in dimensionTableNames"
            :key="name"
            class="rounded-xl px-4 py-3 text-left text-sm transition-colors"
            :class="selectedDimensionTable === name
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-neutral-700 hover:bg-neutral-100'"
            @click="selectDimensionTable(name)"
          >
            {{ TAB_LABELS[name] }}
            <span class="ml-1 text-xs text-neutral-400">{{ name }}</span>
          </button>
        </nav>
      </div>
```

- [ ] **Step 3: Add conditional main content for dictionary view**

In the `<main>` section, after the header (around line 89, right before `<div class="relative flex min-h-0 flex-1 flex-col px-3...`), wrap the existing chat content block with a `v-if="sidebarTab === 'chat'"`, and add the dictionary view after. Replace:

```html
      <div class="relative flex min-h-0 flex-1 flex-col px-3 pb-3 pt-3 sm:px-5 lg:px-8 lg:pb-6">
        <div v-if="currentSession && contextWarning" ...>...</div>
        <MessageList v-if="currentSession" ... />
        <WelcomeDashboard v-else ... />
      </div>
      <div v-if="currentSession" class="relative z-10 ...">...</div>
```

With:

```html
      <!-- 对话主内容 -->
      <template v-if="sidebarTab === 'chat'">
        <div class="relative flex min-h-0 flex-1 flex-col px-3 pb-3 pt-3 sm:px-5 lg:px-8 lg:pb-6">
          <div
            v-if="currentSession && contextWarning"
            class="animate-fade-in mx-auto mb-3 w-full max-w-5xl rounded-[22px] border border-amber-200/80 bg-amber-50/95 px-4 py-3 text-sm text-amber-900 shadow-sm"
          >
            <p class="font-semibold">当前上下文已接近安全阈值，建议新建对话。</p>
            <p class="mt-1 text-amber-800/90">
              估算输入 {{ contextWarning.estimated_input_tokens }} tokens，预警线 {{ contextWarning.warn_tokens }}，模型窗口 {{ contextWarning.context_window }}。
            </p>
          </div>

          <MessageList v-if="currentSession" ref="messageListRef" @select-scenario="handleSelectScenario" />
          <WelcomeDashboard v-else @submit="handleDashboardSubmit" />
        </div>

        <div
          v-if="currentSession"
          class="relative z-10 border-t border-neutral-200/70 bg-white/70 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.5rem)] pt-2 backdrop-blur-xl sm:px-5 lg:px-8 lg:pt-3"
        >
          <div class="mx-auto w-full max-w-5xl panel p-2.5 sm:p-3">
            <div class="mb-2 flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
              <ToggleSwitch
                v-model="streamMode"
                label="流式输出"
                :show-status="true"
                on-label="实时显示"
                off-label="等待完整回复"
              />
              <span
                v-if="isSending"
                class="inline-flex items-center gap-1.5 self-start rounded-full px-2.5 py-0.5 text-[11px] font-medium sm:self-auto"
                :class="streamMode ? 'bg-primary/10 text-primary' : 'bg-neutral-100 text-neutral-500'"
              >
                <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ streamMode ? '流式响应中...' : '发送中...' }}
              </span>
            </div>

            <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div class="relative flex-1">
                <textarea
                  v-model="inputText"
                  @keydown.enter.exact.prevent="handleSendMessage"
                  @keydown.enter.shift="inputText += '\n'"
                  placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                  class="input min-h-[44px] resize-none pr-14"
                  rows="1"
                  :disabled="isSending"
                />
                <div
                  v-if="inputText.length > 0"
                  class="absolute bottom-2.5 right-3.5 rounded-full bg-white/90 px-2 py-0.5 text-[10px] text-neutral-500 shadow-sm"
                >
                  {{ inputText.length }} 字符
                </div>
              </div>

              <button
                @click="isSending && streamMode ? handleStopStreaming() : handleSendMessage()"
                :disabled="!isSending && !inputText.trim()"
                class="flex h-10 items-center justify-center gap-1.5 rounded-2xl px-4 text-sm font-medium transition-all duration-200 sm:min-w-[110px]"
                :class="isSending && streamMode
                  ? 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200 active:scale-[0.98]'
                  : 'btn-primary'"
              >
                <svg v-if="!isSending" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <svg v-else-if="streamMode" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 7h10v10H7z" />
                </svg>
                {{ isSending ? (streamMode ? '停止生成' : '发送中') : '发送' }}
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- 数据字典主内容 -->
      <div v-else class="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <!-- 未选择表时的占位提示 -->
        <div v-if="!selectedDimensionTable" class="flex flex-1 items-center justify-center">
          <div class="text-center">
            <svg class="mx-auto h-12 w-12 text-neutral-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            <p class="mt-4 text-sm text-neutral-500">请从左侧选择一张维度表查看</p>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-else-if="dimensionLoading" class="flex flex-1 items-center justify-center">
          <p class="text-sm text-neutral-500">加载中...</p>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="dimensionError" class="flex flex-1 items-center justify-center">
          <div class="text-center">
            <p class="text-sm text-red-600">{{ dimensionError }}</p>
            <button
              class="mt-3 rounded-xl border border-neutral-200 px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-50"
              @click="selectDimensionTable(selectedDimensionTable!)"
            >
              重试
            </button>
          </div>
        </div>

        <!-- 数据表格 -->
        <DimensionTable
          v-else-if="dimensionData"
          :title="TAB_LABELS[dimensionData.table_name] || dimensionData.table_name"
          :columns="dimensionData.columns"
          :rows="dimensionData.rows"
        />
      </div>
```

- [ ] **Step 4: Verify TypeScript compilation**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ChatView.vue
git commit -m "feat: add data dictionary sidebar tab in ChatView"
```
