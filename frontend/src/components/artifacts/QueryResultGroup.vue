<!-- frontend/src/components/artifacts/QueryResultGroup.vue -->
<template>
  <div v-if="tables && tables.length > 0" class="w-full space-y-2 text-left animate-fade-in">
    <!-- 多表格：Tab 分组切换容器 -->
    <div
      v-if="tables.length > 1"
      class="rounded-2xl border border-neutral-200/80 bg-white/95 shadow-sm overflow-hidden"
    >
      <!-- 头部 Tab 导航栏 -->
      <div class="flex items-center justify-between border-b border-neutral-200/60 bg-neutral-50/70 px-4 py-2.5">
        <div class="flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5">
          <button
            v-for="(t, idx) in tables"
            :key="t.tool_call_id || idx"
            type="button"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150 cursor-pointer shrink-0"
            :class="[
              activeIdx === idx
                ? 'bg-primary text-white shadow-sm'
                : 'text-neutral-600 hover:bg-neutral-200/60 hover:text-neutral-900 bg-white border border-neutral-200/70'
            ]"
            @click="switchTable(idx)"
          >
            <span>📋</span>
            <span>{{ formatSubagentTitle(t.subagent_name || t.created_by) }}</span>
            <span class="opacity-80 text-[11px]">({{ getRowCount(t) }} 行)</span>
          </button>
        </div>

        <div class="flex items-center gap-2 pl-3 text-xs text-neutral-500 font-medium shrink-0">
          <span class="rounded-lg bg-neutral-100 px-2 py-0.5 text-[11px] text-neutral-600">
            共 {{ tables.length }} 个数据表
          </span>
        </div>
      </div>

      <!-- 当前表格内容区 -->
      <div class="p-3 bg-neutral-50/30">
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
          class="mt-2.5 flex items-start gap-1.5 rounded-xl bg-amber-50/70 p-2.5 text-[11px] leading-relaxed text-amber-800 border border-amber-200/60"
        >
          <span class="text-[13px] leading-none">⚠️</span>
          <div>
            数据行数过多，页面仅承载展示前 {{ allCurrentRows.length }} 行预览。如需获取完整分析结果，请使用 <strong>导出 CSV</strong> 或 <strong>聚合 SQL</strong> 重跑。
          </div>
        </div>
      </div>
    </div>

    <!-- 单表格：直接展示带分页控制 -->
    <div v-else class="w-full">
      <TableResult
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

      <!-- 单表格防御性截断提示 -->
      <div
        v-if="currentIsTruncated"
        class="mt-2 flex items-start gap-1.5 rounded-xl bg-amber-50/70 p-2.5 text-[11px] leading-relaxed text-amber-800 border border-amber-200/60"
      >
        <span class="text-[13px] leading-none">⚠️</span>
        <div>
          数据行数过多，页面仅承载展示前 {{ allCurrentRows.length }} 行预览。如需获取完整分析结果，请使用 <strong>导出 CSV</strong> 或 <strong>聚合 SQL</strong> 重跑。
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

const props = defineProps<{
  tables: QueryResultItem[]
}>()

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
