# 快捷场景面板 (Phase 4: Frontend Result Renderers & Main Panel Drawer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建快捷场景面板结果分发器组件（`TableResult`, `ScalarResult`, `ResultRenderer`）、场景树筛选列表组件 `ScenarioList.vue`，以及主面板抽屉容器 `ScenarioPanel.vue`。

**Architecture:** `TableResult` 封装原有的 `DimensionTable` 表格渲染，`ScalarResult` 渲染大字指标。`ResultRenderer` 统一处理 Loading 骨架屏、Error 提示与 Retry，并根据 `output_type` 分发渲染。`ScenarioPanel.vue` 集成 Header 顶部按钮、模板 Tabs 切换条与场景切页。

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Pinia Store, Tailwind CSS.

---

## File Structure

- **Create**: [TableResult.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/TableResult.vue) (Renders query result as responsive data table, handling double-click cell events)
- **Create**: [ScalarResult.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ScalarResult.vue) (Renders metric value as large summary scalar card)
- **Create**: [ResultRenderer.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ResultRenderer.vue) (Handles loading skeleton state, error message & retry, and dispatches to TableResult/ScalarResult)
- **Create**: [ScenarioList.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ScenarioList.vue) (Domain-grouped scenario list with search filtering)
- **Create**: [ScenarioPanel.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ScenarioPanel.vue) (Main drawer slide-over container with controls, template Tabs bar, ParameterForm, and ResultRenderer)

---

### Task 1: Create `TableResult.vue` and `ScalarResult.vue`

**Files:**
- Create: `frontend/src/components/TableResult.vue`
- Create: `frontend/src/components/ScalarResult.vue`

- [ ] **Step 1: Create `TableResult.vue`**

```vue
<!-- frontend/src/components/TableResult.vue -->
<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between px-1 text-xs text-slate-400">
      <span>共 {{ rowCount }} 条记录</span>
      <span class="text-[11px] text-slate-500">双击单元格填入聊天输入框</span>
    </div>

    <div class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 max-h-96">
      <table class="w-full text-left text-xs border-collapse">
        <thead class="sticky top-0 bg-slate-800/90 backdrop-blur z-10">
          <tr class="border-b border-slate-700">
            <th
              v-for="col in columns"
              :key="col"
              class="px-3 py-2 font-medium text-slate-300 whitespace-nowrap cursor-pointer select-none hover:text-indigo-300"
              title="双击可填入输入框"
              @dblclick="$emit('cell-dblclick', String(col))"
            >
              {{ col }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/80">
          <tr
            v-for="(row, rIdx) in rows"
            :key="rIdx"
            class="hover:bg-slate-800/40 transition-colors"
          >
            <td
              v-for="(cell, cIdx) in row"
              :key="cIdx"
              class="px-3 py-2 text-slate-300 whitespace-nowrap cursor-pointer hover:bg-indigo-950/30"
              title="双击可填入输入框"
              @dblclick="$emit('cell-dblclick', String(cell))"
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
  columns: string[]
  rows: (string | number)[][]
  rowCount: number
}>()

defineEmits<{
  (e: 'cell-dblclick', value: string): void
}>()
</script>
```

- [ ] **Step 2: Create `ScalarResult.vue`**

```vue
<!-- frontend/src/components/ScalarResult.vue -->
<template>
  <div class="flex flex-col items-center justify-center p-8 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
    <span class="text-xs font-medium text-slate-400">{{ label || '查询指标' }}</span>
    <span class="text-4xl font-extrabold text-indigo-400 tracking-tight font-mono">
      {{ value }}
    </span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  value: string | number
  label?: string
}>()
</script>
```

---

### Task 2: Create Result Dispatcher `ResultRenderer.vue`

**Files:**
- Create: `frontend/src/components/ResultRenderer.vue`

- [ ] **Step 1: Create `ResultRenderer.vue`**

```vue
<!-- frontend/src/components/ResultRenderer.vue -->
<template>
  <div class="w-full">
    <!-- Loading 骨架屏 -->
    <div v-if="loading" class="space-y-3 p-4 bg-slate-900/40 rounded-xl border border-slate-800/60 animate-pulse">
      <div class="h-4 bg-slate-800 rounded w-1/3"></div>
      <div class="h-24 bg-slate-800/60 rounded w-full"></div>
    </div>

    <!-- Error 状态与重试 -->
    <div v-else-if="error" class="p-4 bg-rose-950/30 border border-rose-900/50 rounded-xl space-y-2">
      <div class="flex items-center space-x-2 text-rose-400 text-xs font-medium">
        <span>⚠️ 查询失败</span>
      </div>
      <p class="text-xs text-rose-300/80">{{ error }}</p>
      <button
        type="button"
        class="px-3 py-1 bg-rose-900/40 hover:bg-rose-900/60 text-rose-200 rounded text-xs transition-colors"
        @click="$emit('retry')"
      >
        重新尝试
      </button>
    </div>

    <!-- 结果分发 -->
    <div v-else-if="result">
      <TableResult
        v-if="result.type === 'table'"
        :columns="result.columns"
        :rows="result.rows"
        :row-count="result.row_count"
        @cell-dblclick="$emit('cell-dblclick', $event)"
      />
      <ScalarResult
        v-else-if="result.type === 'scalar'"
        :value="result.value"
        :label="result.label"
      />
    </div>

    <!-- 空数据提示 -->
    <div v-else class="p-8 text-center text-xs text-slate-500 bg-slate-900/20 rounded-xl border border-dashed border-slate-800">
      请填写参数后点击“执行直通查询”
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ScenarioQueryResult } from '@/api/scenarios'
import TableResult from './TableResult.vue'
import ScalarResult from './ScalarResult.vue'

defineProps<{
  result: ScenarioQueryResult | null
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  (e: 'retry'): void
  (e: 'cell-dblclick', value: string): void
}>()
</script>
```

---

### Task 3: Create Scenario Tree List `ScenarioList.vue`

**Files:**
- Create: `frontend/src/components/ScenarioList.vue`

- [ ] **Step 1: Create `ScenarioList.vue`**

```vue
<!-- frontend/src/components/ScenarioList.vue -->
<template>
  <div class="flex flex-col h-full space-y-3">
    <!-- 搜索框 -->
    <div class="relative">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索快捷场景..."
        class="w-full pl-8 pr-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
      />
      <span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">🔍</span>
    </div>

    <!-- 领域分组列表 -->
    <div class="flex-1 overflow-y-auto space-y-4 pr-1">
      <div
        v-for="domain in filteredDomains"
        :key="domain.domain"
        class="space-y-1.5"
      >
        <div class="text-[11px] font-semibold text-slate-400 tracking-wider uppercase px-1">
          {{ domain.domain_title }}
        </div>
        <div class="space-y-1">
          <div
            v-for="scenario in domain.scenarios"
            :key="scenario.name"
            class="p-2.5 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 hover:border-slate-700 transition-all cursor-pointer group"
            @click="$emit('select', domain.domain, scenario.name)"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-slate-200 group-hover:text-indigo-300">
                {{ scenario.title }}
              </span>
              <span class="text-xs text-slate-500 group-hover:translate-x-0.5 transition-transform">→</span>
            </div>
            <p v-if="scenario.description" class="mt-0.5 text-[11px] text-slate-400 line-clamp-1">
              {{ scenario.description }}
            </p>
          </div>
        </div>
      </div>

      <div v-if="filteredDomains.length === 0" class="py-8 text-center text-xs text-slate-500">
        未找到匹配场景
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ScenarioDomainSummary } from '@/api/scenarios'

const props = defineProps<{
  domains: ScenarioDomainSummary[]
}>()

defineEmits<{
  (e: 'select', domain: string, scenario: string): void
}>()

const searchQuery = ref('')

const filteredDomains = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.domains

  return props.domains
    .map((domain) => {
      const matchedScenarios = domain.scenarios.filter(
        (s) => s.title.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
      )
      return {
        ...domain,
        scenarios: matchedScenarios,
      }
    })
    .filter((domain) => domain.scenarios.length > 0)
})
</script>
```

---

### Task 4: Create Main Drawer Container `ScenarioPanel.vue`

**Files:**
- Create: `frontend/src/components/ScenarioPanel.vue`

- [ ] **Step 1: Create `ScenarioPanel.vue`**

```vue
<!-- frontend/src/components/ScenarioPanel.vue -->
<template>
  <div
    v-if="store.visible"
    class="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col transition-all duration-300"
  >
    <!-- Header 工具栏 -->
    <div class="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
      <div class="flex items-center space-x-2">
        <button
          v-if="store.view === 'detail'"
          type="button"
          class="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded transition-colors"
          title="返回场景列表"
          @click="store.backToList()"
        >
          ←
        </button>
        <h3 class="text-sm font-semibold text-slate-100 truncate max-w-[200px]">
          {{ store.view === 'detail' ? store.currentScenarioTitle : '快捷场景面板' }}
        </h3>
      </div>

      <div class="flex items-center space-x-1">
        <button
          v-if="store.view === 'detail'"
          type="button"
          class="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded transition-colors text-xs flex items-center space-x-1"
          title="刷新查询"
          @click="store.refresh()"
        >
          <span>🔄</span>
        </button>
        <button
          type="button"
          class="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded transition-colors text-xs"
          title="关闭面板"
          @click="store.close()"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Content 区域 -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <!-- 场景列表视图 -->
      <ScenarioList
        v-if="store.view === 'list'"
        :domains="store.domains"
        @select="onScenarioSelect"
      />

      <!-- 场景详情视图 (Tab 切换 + 参数表单 + 结果分发) -->
      <div v-else-if="store.view === 'detail'" class="space-y-4">
        <!-- 模板切换 Tabs（若多模板） -->
        <div
          v-if="store.paramsMeta?.templates && store.paramsMeta.templates.length > 1"
          class="flex p-0.5 bg-slate-800 rounded-lg"
        >
          <button
            v-for="tpl in store.paramsMeta.templates"
            :key="tpl.name"
            type="button"
            :class="[
              'flex-1 py-1 text-xs font-medium rounded-md transition-colors',
              store.activeTemplate === tpl.name
                ? 'bg-slate-900 text-indigo-300 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            ]"
            @click="store.switchTemplate(tpl.name)"
          >
            {{ tpl.label }}
          </button>
        </div>

        <!-- 参数表单区 -->
        <div v-if="store.paramsMeta?.parameters" class="p-3 bg-slate-950/40 rounded-xl border border-slate-800/80">
          <ParameterForm
            :parameters="store.paramsMeta.parameters"
            :values="store.currentParamValues"
            :loading="store.isQueryLoading"
            @update:values="store.updateParamValues($event)"
            @submit="store.executeQuery()"
          />
        </div>

        <!-- 结果分发渲染区 -->
        <ResultRenderer
          :result="store.queryResult"
          :loading="store.isQueryLoading"
          :error="store.queryError"
          @retry="store.executeQuery()"
          @cell-dblclick="$emit('cell-dblclick', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useScenarioPanelStore } from '@/stores/scenarioPanel'
import ScenarioList from './ScenarioList.vue'
import ParameterForm from './ParameterForm.vue'
import ResultRenderer from './ResultRenderer.vue'

const store = useScenarioPanelStore()

defineEmits<{
  (e: 'cell-dblclick', value: string): void
}>()

function onScenarioSelect(domain: string, scenario: string) {
  store.selectScenario(domain, scenario)
}
</script>
```

---

## Self-Review Checklist

1. **Spec coverage:** Covers `TableResult`, `ScalarResult`, `ResultRenderer`, `ScenarioList`, and `ScenarioPanel` drawer container.
2. **Placeholder scan:** No TBDs, no TODOs, all code blocks provided.
3. **TypeScript / Vue 3 compliance:** Clean `<script setup>` syntax, type props/emits, and Pinia store integration.
