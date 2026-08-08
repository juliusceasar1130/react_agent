# 快捷场景面板 (Phase 3: Frontend API, Store & Dynamic Form Widgets) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建快捷场景面板前端 TypeScript API 接口调用层、Pinia Setup Store 状态中心，以及通用动态参数表单 `ParameterForm.vue` 与拆分的 `widgets/` 原子控件。

**Architecture:** API 层封装 Axios 请求，匹配后端 `/api/scenarios` 路由。Pinia Store (`useScenarioPanelStore`) 管理抽屉状态、多模板选型、场景参数按场景 Key 缓存机制。动态表单基于 `widget` 类型分发给原子控件（`TextWidget`, `NumberWidget`, `SelectWidget`, `MultiSelectWidget`）。

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Pinia, Axios, Tailwind CSS.

---

## File Structure

- **Create**: [scenarios.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/api/scenarios.ts) (API service methods and TypeScript types matching backend schemas)
- **Create**: [scenarioPanel.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/stores/scenarioPanel.ts) (Pinia Setup Store for managing scenario panel drawer state, parameter cache, selected templates, and query execution)
- **Create**: [TextWidget.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/widgets/TextWidget.vue) (Text input widget)
- **Create**: [NumberWidget.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/widgets/NumberWidget.vue) (Number input widget)
- **Create**: [SelectWidget.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/widgets/SelectWidget.vue) (Dropdown select widget with option support)
- **Create**: [MultiSelectWidget.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/widgets/MultiSelectWidget.vue) (Multi-select tag group widget)
- **Create**: [ParameterForm.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/frontend/src/components/ParameterForm.vue) (Dynamic parameter form container)

---

### Task 1: Create Frontend API Service `frontend/src/api/scenarios.ts`

**Files:**
- Create: `frontend/src/api/scenarios.ts`

- [ ] **Step 1: Write `frontend/src/api/scenarios.ts`**

```typescript
// frontend/src/api/scenarios.ts
import api from './index'

export interface ScenarioItemSummary {
  name: string
  title: string
  description: string
}

export interface ScenarioDomainSummary {
  domain: string
  domain_title: string
  scenarios: ScenarioItemSummary[]
}

export interface ParameterOption {
  value: string
  label: string
}

export interface ParameterDef {
  type: string
  widget: string
  description: string
  required: boolean
  default: string | number | null
  options: ParameterOption[]
}

export interface TemplateInfo {
  name: string
  label: str
}

export interface ScenarioParamsMeta {
  name: string
  title: string
  output_type: string
  templates?: TemplateInfo[]
  default_template?: string
  parameters: Record<string, ParameterDef>
}

export interface TableQueryResult {
  type: 'table'
  columns: string[]
  rows: (string | number)[][]
  row_count: number
}

export interface ScalarQueryResult {
  type: 'scalar'
  value: string | number
  label: string
}

export type ScenarioQueryResult = TableQueryResult | ScalarQueryResult

/**
 * 拉取全量场景领域树列表
 */
export async function getScenariosApi(): Promise<ScenarioDomainSummary[]> {
  const data = await api.get('/api/scenarios')
  return data as unknown as ScenarioDomainSummary[]
}

/**
 * 解析获取指定场景的参数定义与模板
 */
export async function getScenarioParamsApi(
  domain: string,
  scenario: string,
  templateName?: string
): Promise<ScenarioParamsMeta> {
  const params: Record<string, string> = {}
  if (templateName) {
    params.template_name = templateName
  }
  const data = await api.get(`/api/scenarios/${domain}/${scenario}/params`, { params })
  return data as unknown as ScenarioParamsMeta
}

/**
 * 执行快捷场景直通 SQL 查询
 */
export async function executeScenarioApi(
  domain: string,
  scenario: string,
  userParams: Record<string, any>,
  templateName?: string
): Promise<ScenarioQueryResult> {
  const payload = {
    params: userParams,
    template_name: templateName,
  }
  const data = await api.post(`/api/scenarios/${domain}/${scenario}/execute`, payload)
  return data as unknown as ScenarioQueryResult
}
```

- [ ] **Step 2: Verify TypeScript compiles without error**

Run: `cd frontend && npm run build` (or `npx vue-tsc --noEmit`)
Expected: No type errors in `scenarios.ts`.

---

### Task 2: Create Pinia Setup Store `frontend/src/stores/scenarioPanel.ts`

**Files:**
- Create: `frontend/src/stores/scenarioPanel.ts`

- [ ] **Step 1: Write `frontend/src/stores/scenarioPanel.ts`**

```typescript
// frontend/src/stores/scenarioPanel.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getScenariosApi,
  getScenarioParamsApi,
  executeScenarioApi,
  type ScenarioDomainSummary,
  type ScenarioParamsMeta,
  type ScenarioQueryResult,
} from '@/api/scenarios'

export const useScenarioPanelStore = defineStore('scenarioPanel', () => {
  // 面板显隐与视图状态 ('list' | 'detail')
  const visible = ref(false)
  const view = ref<'list' | 'detail'>('list')

  // 全量场景分类树
  const domains = ref<ScenarioDomainSummary[]>([])
  const isDomainsLoading = ref(false)
  const domainsError = ref<string | null>(null)

  // 选中场景与模板状态
  const selectedDomain = ref<string | null>(null)
  const selectedScenario = ref<string | null>(null)
  const activeTemplate = ref<string | null>(null)

  // 当前场景元数据与参数设置
  const paramsMeta = ref<ScenarioParamsMeta | null>(null)
  const isParamsLoading = ref(false)
  const paramsError = ref<string | null>(null)

  // 参数缓存按 `${domain}/${scenario}/${template}` Key 存储
  const paramValuesCache = ref<Record<string, Record<string, any>>>({})
  const currentParamValues = ref<Record<string, any>>({})

  // 查询结果与状态
  const queryResult = ref<ScenarioQueryResult | null>(null)
  const isQueryLoading = ref(false)
  const queryError = ref<string | null>(null)

  // 计算属性：当前选中场景标题
  const currentScenarioTitle = computed(() => {
    return paramsMeta.value?.title || selectedScenario.value || ''
  })

  // Action: 打开面板
  function open(targetDomain?: string, targetScenario?: string) {
    visible.value = true
    if (domains.value.length === 0) {
      fetchDomainTree()
    }
    if (targetDomain && targetScenario) {
      selectScenario(targetDomain, targetScenario)
    }
  }

  // Action: 关闭面板
  function close() {
    visible.value = false
  }

  // Action: 切换至场景列表视图
  function backToList() {
    view.value = 'list'
  }

  // Action: 拉取场景分类树
  async function fetchDomainTree() {
    isDomainsLoading.value = true
    domainsError.value = null
    try {
      domains.value = await getScenariosApi()
    } catch (err: any) {
      domainsError.value = err.message || '获取场景列表失败'
    } finally {
      isDomainsLoading.value = false
    }
  }

  // Action: 选中场景并初始化参数
  async function selectScenario(domain: string, scenario: string, templateName?: string) {
    selectedDomain.value = domain
    selectedScenario.value = scenario
    view.value = 'detail'
    queryResult.value = null
    queryError.value = null

    await loadScenarioParams(domain, scenario, templateName)
  }

  // Action: 加载参数元数据
  async function loadScenarioParams(domain: string, scenario: string, templateName?: string) {
    isParamsLoading.value = true
    paramsError.value = null
    try {
      const meta = await getScenarioParamsApi(domain, scenario, templateName)
      paramsMeta.value = meta
      activeTemplate.value = meta.default_template || (meta.templates?.[0]?.name ?? null)

      // 从缓存恢复或应用默认值
      const cacheKey = `${domain}/${scenario}/${activeTemplate.value || 'default'}`
      if (paramValuesCache.value[cacheKey]) {
        currentParamValues.value = { ...paramValuesCache.value[cacheKey] }
      } else {
        const initialValues: Record<string, any> = {}
        if (meta.parameters) {
          for (const [key, pDef] of Object.entries(meta.parameters)) {
            initialValues[key] = pDef.default ?? ''
          }
        }
        currentParamValues.value = initialValues
        paramValuesCache.value[cacheKey] = { ...initialValues }
      }

      // 自动发第一次直通查询
      await executeQuery()
    } catch (err: any) {
      paramsError.value = err.message || '获取场景参数失败'
    } finally {
      isParamsLoading.value = false
    }
  }

  // Action: 切换模板 Tab
  async function switchTemplate(newTemplateName: string) {
    if (!selectedDomain.value || !selectedScenario.value) return
    activeTemplate.value = newTemplateName
    await loadScenarioParams(selectedDomain.value, selectedScenario.value, newTemplateName)
  }

  // Action: 更新参数值
  function updateParamValues(newValues: Record<string, any>) {
    currentParamValues.value = { ...newValues }
    if (selectedDomain.value && selectedScenario.value) {
      const cacheKey = `${selectedDomain.value}/${selectedScenario.value}/${activeTemplate.value || 'default'}`
      paramValuesCache.value[cacheKey] = { ...newValues }
    }
  }

  // Action: 执行直通 SQL 查询
  async function executeQuery() {
    if (!selectedDomain.value || !selectedScenario.value) return
    isQueryLoading.value = true
    queryError.value = null
    try {
      const res = await executeScenarioApi(
        selectedDomain.value,
        selectedScenario.value,
        currentParamValues.value,
        activeTemplate.value || undefined
      )
      queryResult.value = res
    } catch (err: any) {
      queryError.value = err.message || '直通查询执行失败'
      queryResult.value = null
    } finally {
      isQueryLoading.value = false
    }
  }

  // Action: 刷新当前查询
  async function refresh() {
    await executeQuery()
  }

  return {
    visible,
    view,
    domains,
    isDomainsLoading,
    domainsError,
    selectedDomain,
    selectedScenario,
    activeTemplate,
    paramsMeta,
    isParamsLoading,
    paramsError,
    currentParamValues,
    queryResult,
    isQueryLoading,
    queryError,
    currentScenarioTitle,
    open,
    close,
    backToList,
    fetchDomainTree,
    selectScenario,
    switchTemplate,
    updateParamValues,
    executeQuery,
    refresh,
  }
})
```

---

### Task 3: Create Modular Input Widgets in `frontend/src/components/widgets/`

**Files:**
- Create: `frontend/src/components/widgets/TextWidget.vue`
- Create: `frontend/src/components/widgets/NumberWidget.vue`
- Create: `frontend/src/components/widgets/SelectWidget.vue`
- Create: `frontend/src/components/widgets/MultiSelectWidget.vue`

- [ ] **Step 1: Create `TextWidget.vue`**

```vue
<!-- frontend/src/components/widgets/TextWidget.vue -->
<template>
  <input
    type="text"
    :value="modelValue"
    :placeholder="paramDef.description || '请输入文本'"
    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

defineProps<{
  modelValue: string
  paramDef: ParameterDef
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>
```

- [ ] **Step 2: Create `NumberWidget.vue`**

```vue
<!-- frontend/src/components/widgets/NumberWidget.vue -->
<template>
  <input
    type="number"
    :value="modelValue"
    :placeholder="paramDef.description || '请输入数字'"
    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
    @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
  />
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

defineProps<{
  modelValue: string | number
  paramDef: ParameterDef
}>()

defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()
</script>
```

- [ ] **Step 3: Create `SelectWidget.vue`**

```vue
<!-- frontend/src/components/widgets/SelectWidget.vue -->
<template>
  <select
    :value="modelValue"
    class="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors cursor-pointer"
    @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
  >
    <option
      v-for="opt in paramDef.options"
      :key="opt.value"
      :value="opt.value"
    >
      {{ opt.label }}
    </option>
  </select>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

defineProps<{
  modelValue: string
  paramDef: ParameterDef
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>
```

- [ ] **Step 4: Create `MultiSelectWidget.vue`**

```vue
<!-- frontend/src/components/widgets/MultiSelectWidget.vue -->
<template>
  <div class="flex flex-wrap gap-1.5">
    <button
      v-for="opt in paramDef.options"
      :key="opt.value"
      type="button"
      :class="[
        'px-2.5 py-1 text-xs rounded border transition-colors',
        isSelected(opt.value)
          ? 'bg-indigo-600 border-indigo-500 text-white font-medium'
          : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
      ]"
      @click="toggleValue(opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'

const props = defineProps<{
  modelValue: string[] | string
  paramDef: ParameterDef
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

function currentArray(): string[] {
  if (Array.isArray(props.modelValue)) return props.modelValue
  if (typeof props.modelValue === 'string' && props.modelValue) return props.modelValue.split(',')
  return []
}

function isSelected(val: string): boolean {
  return currentArray().includes(val)
}

function toggleValue(val: string) {
  const arr = [...currentArray()]
  const idx = arr.indexOf(val)
  if (idx >= 0) {
    arr.splice(idx, 1)
  } else {
    arr.push(val)
  }
  emit('update:modelValue', arr)
}
</script>
```

---

### Task 4: Create Generic Parameter Form Container `frontend/src/components/ParameterForm.vue`

**Files:**
- Create: `frontend/src/components/ParameterForm.vue`

- [ ] **Step 1: Create `ParameterForm.vue`**

```vue
<!-- frontend/src/components/ParameterForm.vue -->
<template>
  <form class="space-y-3" @submit.prevent="$emit('submit')">
    <div
      v-for="(pDef, pKey) in parameters"
      :key="pKey"
      class="flex flex-col space-y-1"
    >
      <label class="text-xs font-medium text-slate-400 flex items-center justify-between">
        <span>{{ pKey }}</span>
        <span v-if="pDef.description" class="text-[11px] text-slate-500 font-normal">
          {{ pDef.description }}
        </span>
      </label>

      <!-- 动态部件分发 -->
      <component
        :is="getWidgetComponent(pDef.widget)"
        :model-value="values[pKey] ?? ''"
        :param-def="pDef"
        @update:model-value="onValueChange(pKey as string, $event)"
      />
    </div>

    <!-- 提交按钮区 -->
    <div class="pt-2 flex items-center justify-end space-x-2">
      <button
        type="submit"
        :disabled="loading"
        class="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1.5"
      >
        <span v-if="loading" class="animate-spin text-xs">🌀</span>
        <span>执行直通查询</span>
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import type { ParameterDef } from '@/api/scenarios'
import TextWidget from './widgets/TextWidget.vue'
import NumberWidget from './widgets/NumberWidget.vue'
import SelectWidget from './widgets/SelectWidget.vue'
import MultiSelectWidget from './widgets/MultiSelectWidget.vue'

const props = defineProps<{
  parameters: Record<string, ParameterDef>
  values: Record<string, any>
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:values', values: Record<string, any>): void
  (e: 'submit'): void
}>()

function getWidgetComponent(widget: string) {
  switch (widget) {
    case 'number':
      return NumberWidget
    case 'select':
      return SelectWidget
    case 'multiselect':
      return MultiSelectWidget
    case 'text':
    default:
      return TextWidget
  }
}

function onValueChange(key: string, val: any) {
  const updated = { ...props.values, [key]: val }
  emit('update:values', updated)
}
</script>
```

---

## Self-Review Checklist

1. **Spec coverage:** Covers `scenarios.ts` API layer, Pinia Store `scenarioPanel.ts`, 4 widget components in `widgets/`, and container `ParameterForm.vue`.
2. **Placeholder scan:** No TBDs, no TODOs, all code blocks provided.
3. **TypeScript / Vue 3 compliance:** Using `<script setup>` syntax, TypeScript interfaces, and reactivity primitives.
