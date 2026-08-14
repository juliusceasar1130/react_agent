<!-- frontend/src/components/ResultRenderer.vue -->
<template>
  <div class="w-full h-full flex flex-col min-h-0">
    <!-- Loading 骨架屏 -->
    <div v-if="loading" class="space-y-3 p-5 bg-white/70 rounded-2xl border border-neutral-200/80 shadow-sm animate-pulse">
      <div class="h-4 bg-neutral-200/80 rounded w-1/3"></div>
      <div class="h-24 bg-neutral-100 rounded w-full"></div>
    </div>

    <!-- Error 状态与重试 -->
    <div v-else-if="error" class="p-4 bg-rose-50/90 border border-rose-200 rounded-2xl space-y-2">
      <div class="flex items-center space-x-2 text-rose-700 text-xs font-semibold">
        <span>⚠️ 查询失败</span>
      </div>
      <p class="text-xs text-rose-600/90">{{ error }}</p>
      <button
        type="button"
        class="px-3 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-xl text-xs font-medium transition-colors cursor-pointer"
        @click="$emit('retry')"
      >
        重新尝试
      </button>
    </div>

    <!-- 结果分发 -->
    <div v-else-if="result" class="h-full flex flex-col min-h-0">
      <TableResult
        v-if="result.type === 'table'"
        :columns="result.columns"
        :rows="result.rows"
        :row-count="result.row_count"
        :total-count="result.total_count"
        :page="result.page"
        :page-size="result.page_size"
        :total-pages="result.total_pages"
        :is-truncated="result.is_truncated"
        class="h-full flex flex-col min-h-0"
        @change-page="$emit('changePage', $event)"
        @change-page-size="$emit('changePageSize', $event)"
      />
      <ScalarResult
        v-else-if="result.type === 'scalar'"
        :value="result.value"
        :label="result.label"
      />
    </div>

    <!-- 空数据提示 -->
    <div v-else class="p-8 text-center text-xs text-neutral-400 bg-white/50 rounded-2xl border border-dashed border-neutral-200 my-auto">
      请填写参数后点击“查询”
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
  (e: 'changePage', page: number): void
  (e: 'changePageSize', size: number): void
}>()
</script>
