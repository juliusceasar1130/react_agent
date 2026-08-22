<!-- frontend/src/components/artifacts/QueryResultGroup.vue -->
<template>
  <div v-if="tables && tables.length > 0" class="w-full space-y-2 text-left animate-fade-in">
    <!-- 折叠卡片容器 -->
    <div
      class="rounded-2xl border border-neutral-200/80 bg-white/95 shadow-2xs overflow-hidden dark:border-neutral-800 dark:bg-neutral-900/90 transition-all duration-200"
    >
      <!-- 统一折叠/展开头部栏 -->
      <button
        type="button"
        class="flex w-full cursor-pointer items-center justify-between px-3.5 py-2.5 bg-neutral-50/80 hover:bg-neutral-100/70 dark:bg-neutral-800/60 dark:hover:bg-neutral-800/90 transition-colors border-0 text-left select-none"
        @click="toggleExpand"
      >
        <div class="flex items-center gap-2 min-w-0">
          <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>

          <span class="text-xs font-semibold text-neutral-800 dark:text-neutral-200 truncate">
            {{ headerTitle }}
          </span>

          <span class="inline-flex items-center rounded-full bg-neutral-200/70 dark:bg-neutral-700/60 px-2 py-0.5 text-[11px] font-medium text-neutral-600 dark:text-neutral-300 shrink-0 font-mono">
            {{ totalRowsSummary }}
          </span>

          <span
            v-if="tables.length > 1"
            class="hidden sm:inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary shrink-0"
          >
            共 {{ tables.length }} 个数据表
          </span>

          <span
            v-if="currentIsTruncated"
            class="inline-flex items-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 px-2 py-0.5 text-[10px] font-medium shrink-0"
          >
            受保护截断
          </span>
        </div>

        <div class="flex items-center gap-1.5 text-neutral-400 shrink-0 ml-2">
          <span class="text-[11px] font-normal text-neutral-400">
            {{ isExpanded ? '收起表格' : '展开查看数据' }}
          </span>
          <svg
            class="h-4 w-4 transition-transform duration-200"
            :class="{ 'rotate-180': isExpanded }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      <!-- 展开后的表格主体内容 -->
      <div v-show="isExpanded" class="border-t border-neutral-200/60 dark:border-neutral-800">
        <!-- 多表格：Tab 分组切换导航条 -->
        <div
          v-if="tables.length > 1"
          class="flex items-center justify-between border-b border-neutral-200/60 bg-neutral-50/50 dark:bg-neutral-800/40 px-3.5 py-2"
        >
          <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
            <button
              v-for="(t, idx) in tables"
              :key="t.tool_call_id || idx"
              type="button"
              class="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition-all duration-150 cursor-pointer shrink-0"
              :class="[
                activeIdx === idx
                  ? 'bg-primary text-white shadow-xs'
                  : 'text-neutral-600 dark:text-neutral-300 hover:bg-neutral-200/60 dark:hover:bg-neutral-700/60 bg-white dark:bg-neutral-800 border border-neutral-200/70 dark:border-neutral-700'
              ]"
              @click="switchTable(idx)"
            >
              <span>📋</span>
              <span>{{ formatSubagentTitle(t.subagent_name || t.created_by) }}</span>
              <span class="opacity-80 text-[11px]">({{ getRowCount(t) }} 行)</span>
            </button>
          </div>

          <div class="flex items-center gap-2 pl-3 text-xs text-neutral-500 font-medium shrink-0">
            <span class="rounded-lg bg-neutral-100 dark:bg-neutral-800 px-2 py-0.5 text-[11px] text-neutral-600 dark:text-neutral-400">
              共 {{ tables.length }} 个数据表
            </span>
          </div>
        </div>

        <!-- 表格组件渲染区 -->
        <div class="p-3 bg-neutral-50/30 dark:bg-neutral-900/30">
          <TableResult
            v-if="currentTable"
            :columns="currentColumns"
            :rows="currentPagedRows"
            :row-count="currentDisplayRowCount"
            :total-count="currentTotalCount"
            :page="currentPage"
            :page-size="currentPageSize"
            :total-pages="currentTotalPages"
            :is-truncated="currentIsTruncated"
            @change-page="handlePageChange"
            @change-page-size="handlePageSizeChange"
          />

          <!-- 防御性截断提示 -->
          <div
            v-if="currentIsTruncated"
            class="mt-2.5 flex items-start gap-1.5 rounded-xl bg-amber-50/70 dark:bg-amber-950/40 p-2.5 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300 border border-amber-200/60 dark:border-amber-900/50"
          >
            <span class="text-[13px] leading-none">⚠️</span>
            <div>
              数据行数过多，页面仅承载展示前 {{ allCurrentRows.length }} 行预览。如需获取完整分析结果，请使用 <strong>导出 CSV</strong> 或 <strong>聚合 SQL</strong> 重跑。
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import TableResult from '@/components/artifacts/TableResult.vue'
import { formatSubagentTitle } from '@/utils/helpers'

export interface QueryResultItem {
  kind?: string
  tool_call_id?: string
  subagent_name?: string
  created_by?: string
  columns?: string[]
  rows?: (string | number)[][]
  row_count?: number
  total_count?: number
  is_truncated?: boolean
}

const props = withDefaults(
  defineProps<{
    tables: QueryResultItem[]
    defaultExpanded?: boolean
  }>(),
  {
    defaultExpanded: false,
  },
)

// 默认收起表格，避免占满大屏空间
const isExpanded = ref(props.defaultExpanded)

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const activeIdx = ref(0)
const currentPage = ref(1)
const currentPageSize = ref(50)

const switchTable = (idx: number) => {
  activeIdx.value = idx
  currentPage.value = 1
}

watch(
  () => props.tables.length,
  (newLen) => {
    if (activeIdx.value >= newLen) {
      activeIdx.value = Math.max(0, newLen - 1)
      currentPage.value = 1
    }
  },
)

const currentTable = computed<QueryResultItem | null>(() => {
  if (!props.tables || props.tables.length === 0) return null
  return props.tables[activeIdx.value] || props.tables[0]
})

const getRowCount = (t: QueryResultItem): number => {
  if (t.total_count !== undefined && t.total_count > 0) return t.total_count
  if (t.row_count !== undefined && t.row_count > 0) return t.row_count
  return t.rows?.length || 0
}

const currentColumns = computed<string[]>(() => {
  return currentTable.value?.columns || []
})

const allCurrentRows = computed<(string | number)[][]>(() => {
  return currentTable.value?.rows || []
})

const currentTotalCount = computed<number>(() => {
  const t = currentTable.value
  if (!t) return 0
  if (t.total_count !== undefined && t.total_count > 0) return t.total_count
  if (t.row_count !== undefined && t.row_count > 0) return t.row_count
  return allCurrentRows.value.length
})

const currentTotalPages = computed<number>(() => {
  const total = allCurrentRows.value.length
  return Math.max(1, Math.ceil(total / currentPageSize.value))
})

const currentPagedRows = computed<(string | number)[][]>(() => {
  const rows = allCurrentRows.value
  if (rows.length <= currentPageSize.value) return rows
  const start = (currentPage.value - 1) * currentPageSize.value
  return rows.slice(start, start + currentPageSize.value)
})

const currentDisplayRowCount = computed<number>(() => {
  return currentPagedRows.value.length
})

const currentIsTruncated = computed<boolean>(() => {
  return Boolean(currentTable.value?.is_truncated)
})

const headerTitle = computed<string>(() => {
  if (props.tables.length > 1) {
    return 'SQL 查询数据结果'
  }
  const creator = currentTable.value?.subagent_name || currentTable.value?.created_by
  if (creator && creator !== 'sql_domain_agent' && creator !== 'main') {
    return `${formatSubagentTitle(creator)} 查询数据`
  }
  return 'SQL 查询数据预览'
})

const totalRowsSummary = computed<string>(() => {
  if (props.tables.length > 1) {
    const total = props.tables.reduce((sum, t) => sum + getRowCount(t), 0)
    return `共 ${total} 行数据`
  }
  const count = currentTotalCount.value
  const colCount = currentColumns.value.length
  if (colCount > 0) {
    return `共 ${count} 行 × ${colCount} 列`
  }
  return `共 ${count} 行`
})

const handlePageChange = (page: number) => {
  currentPage.value = Math.max(1, Math.min(page, currentTotalPages.value))
}

const handlePageSizeChange = (size: number) => {
  currentPageSize.value = size
  currentPage.value = 1
}
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
