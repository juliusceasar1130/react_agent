# 快捷场景面板 (Phase 5: UI Integration & End-to-End Verification) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将快捷场景面板接入全局 UI 框架，在 Header 中增加“快捷场景”入口，在 WelcomeDashboard 场景卡片增加“快速查看”直达按纽，挂载 `ScenarioPanel.vue`，并进行端到端全量功能与全自动化测试验证。

**Architecture:** 在 `ChatView.vue` Header 中添加“快捷场景”按钮触发 `scenarioPanelStore.open()`。在 `WelcomeDashboard.vue` 的场景标题栏处添加“⚡ 快速查看”按钮触发 `quick-view(domain, scenario)` 事件。在 `VariantB.vue` 中挂载 `ScenarioPanel.vue` 抽屉并绑定 `cell-dblclick` 双击插值。

**Tech Stack:** Vue 3, Pinia, Tailwind CSS, Vite.

---

## File Structure

- **Modify**: [WelcomeDashboard.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/WelcomeDashboard.vue) (Add "快速查看" button on scenario items emitting `quick-view`)
- **Modify**: [ChatView.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/views/ChatView.vue) (Add "快捷场景" header button, handle `quick-view` event from WelcomeDashboard)
- **Modify**: [VariantB.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/VariantB.vue) (Import and mount `ScenarioPanel.vue` drawer)

---

### Task 1: Add "快速查看" Quick-View Button in `WelcomeDashboard.vue`

**Files:**
- Modify: `frontend/src/components/WelcomeDashboard.vue:77 border-l-2`

- [ ] **Step 1: Update `WelcomeDashboard.vue` to declare `quick-view` emit and add button**

```vue
<!-- Modify frontend/src/components/WelcomeDashboard.vue -->
<template>
  <!-- ... -->
  <div v-for="scenario in domain.scenarios" :key="scenario.name" class="relative pl-6 border-l-2 border-neutral-100 group-hover:border-primary/20 transition-colors">
    <div class="absolute -left-[9px] top-0 h-4 w-4 rounded-full bg-white border-2 border-neutral-200 group-hover:border-primary/40 transition-colors"></div>
    <div class="flex items-center justify-between">
      <h4 class="text-sm font-bold text-neutral-800 flex items-center gap-2">
        {{ scenario.title }}
      </h4>
      <button
        type="button"
        @click.stop="$emit('quick-view', domain.name, scenario.name)"
        class="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300 dark:hover:bg-indigo-900/60 px-2 py-0.5 rounded transition cursor-pointer flex items-center space-x-1"
        title="直接查询结果（绕过 LLM Agent）"
      >
        <span>⚡</span>
        <span>快速查看</span>
      </button>
    </div>
    <!-- ... -->
  </div>
</template>

<script setup lang="ts">
// Update defineEmits:
const emit = defineEmits<{
  (e: 'submit', prompt: string): void
  (e: 'quick-view', domain: string, scenario: string): void
}>()
</script>
```

---

### Task 2: Add "快捷场景" Header Entry in `ChatView.vue` and Wire Events

**Files:**
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: Update `ChatView.vue` to import `useScenarioPanelStore` and add Header button + event binding**

```vue
<!-- In frontend/src/views/ChatView.vue Header section -->
<button
  @click="scenarioPanelStore.open()"
  class="flex items-center gap-1.5 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-2 text-xs font-bold text-indigo-500 hover:bg-indigo-600 hover:text-white transition-all duration-200 shadow-sm whitespace-nowrap cursor-pointer"
  title="打开快捷场景面板"
>
  <span>⚡</span>
  <span>快捷场景</span>
</button>

<!-- In WelcomeDashboard component tag -->
<WelcomeDashboard
  v-else
  @submit="handleDashboardSubmit"
  @quick-view="handleQuickView"
/>

<script setup lang="ts">
import { useScenarioPanelStore } from '@/stores/scenarioPanel'

const scenarioPanelStore = useScenarioPanelStore()

function handleQuickView(domain: string, scenario: string) {
  scenarioPanelStore.open(domain, scenario)
}
</script>
```

---

### Task 3: Mount `ScenarioPanel.vue` in `VariantB.vue`

**Files:**
- Modify: `frontend/src/components/VariantB.vue`

- [ ] **Step 1: Import `ScenarioPanel.vue` and place component tag in `VariantB.vue`**

```vue
<!-- In frontend/src/components/VariantB.vue template -->
<template>
  <div class="relative flex h-full w-full overflow-hidden">
    <!-- ... existing template ... -->
    <ScenarioPanel @cell-dblclick="$emit('dblclick-cell', $event)" />
  </div>
</template>

<script setup lang="ts">
import ScenarioPanel from './ScenarioPanel.vue'
</script>
```

---

### Task 4: Run Full System Build & Automated Unit/Integration Test Verification

**Files:**
- Test: All backend pytest tests & frontend Vite build

- [ ] **Step 1: Run backend pytest suite**

Run: `D:\000_software_install\miniconda3\envs\py312_agent\python.exe -m pytest backend/tests/test_scenario_quick_panel_api.py backend/tests/test_scenario_quick_panel_engine.py -v`
Expected: 11 passed

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: 0 errors, build succeeds cleanly.

---

## Self-Review Checklist

1. **Spec coverage:** Covers `WelcomeDashboard.vue`, `ChatView.vue`, `VariantB.vue` integration, and full system verification.
2. **Placeholder scan:** No TBDs, no TODOs, all code blocks provided.
3. **TypeScript / Vue 3 compliance:** Vue 3 `<script setup>` syntax and Pinia store usage.
