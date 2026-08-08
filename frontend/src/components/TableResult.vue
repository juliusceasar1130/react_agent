<!-- frontend/src/components/TableResult.vue -->
<template>
  <div class="h-full flex flex-col min-h-0 rounded-2xl border border-neutral-200/80 bg-white/90 shadow-sm overflow-hidden">
    <!-- 单层表格右上角记录数栏 -->
    <div class="flex items-center justify-end px-4 py-2 bg-neutral-50/60 border-b border-neutral-200/60 text-xs text-neutral-500 font-medium shrink-0">
      <span v-if="isTruncated" class="inline-flex items-center space-x-1 font-semibold text-amber-700 bg-amber-50/90 px-2.5 py-0.5 rounded-lg border border-amber-200/80">
        <span>显示前 {{ rowCount }} 条 / 全量共 {{ totalCount }} 条记录</span>
        <span class="text-[10px] text-amber-600/90 font-normal ml-0.5">(受保护截断)</span>
      </span>
      <span v-else-if="totalCount !== undefined && totalCount > 0">
        显示 {{ startRow }}-{{ endRow }} 条 / 共 {{ totalCount }} 条记录
      </span>
      <span v-else>共 {{ rowCount }} 条记录</span>
    </div>

    <!-- 表格内容主体 -->
    <div class="flex-1 min-h-0 overflow-auto">
      <table class="w-full text-center text-xs border-collapse">
        <thead class="sticky top-0 bg-neutral-50/95 backdrop-blur z-10">
          <tr class="border-b border-neutral-200/80">
            <!-- 增加最左侧固定序号列头 -->
            <th class="px-3 py-2.5 font-semibold text-neutral-400 text-center w-12 shrink-0 select-none">
              #
            </th>
            <th
              v-for="col in columns"
              :key="col"
              class="px-3.5 py-2.5 font-semibold text-neutral-700 text-center whitespace-nowrap select-none"
            >
              {{ col }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-neutral-100">
          <tr
            v-for="(row, rIdx) in rows"
            :key="rIdx"
            class="hover:bg-neutral-50/70 transition-colors"
          >
            <!-- 翻页连续计算物理绝对序号 -->
            <td class="px-3 py-2 text-neutral-400 text-center text-[11px] font-mono select-none">
              {{ ((page || 1) - 1) * (pageSize || 50) + rIdx + 1 }}
            </td>
            <td
              v-for="(cell, cIdx) in row"
              :key="cIdx"
              class="px-3.5 py-2 text-neutral-600 text-center whitespace-nowrap"
            >
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 底部分页控制条 -->
    <div
      v-if="totalCount !== undefined && totalCount > 0"
      class="flex flex-col sm:flex-row items-center justify-between gap-2 sm:gap-0 px-4 py-2 bg-neutral-50/90 border-t border-neutral-200/80 text-xs text-neutral-600 shrink-0 select-none"
    >
      <div class="flex items-center space-x-2">
        <span>每页显示</span>
        <select
          :value="pageSize || 50"
          class="px-2 py-1 bg-white border border-neutral-200 rounded-lg text-xs font-medium text-neutral-700 hover:border-neutral-300 focus:outline-none cursor-pointer"
          @change="$emit('changePageSize', Number(($event.target as HTMLSelectElement).value))"
        >
          <option :value="20">20 条</option>
          <option :value="50">50 条</option>
          <option :value="100">100 条</option>
        </select>
      </div>

      <div class="flex items-center space-x-3">
        <button
          type="button"
          :disabled="(page || 1) <= 1"
          class="px-2.5 py-1 rounded-lg border border-neutral-200 bg-white font-medium text-neutral-700 hover:bg-neutral-100 disabled:opacity-40 disabled:hover:bg-white disabled:cursor-not-allowed transition-colors cursor-pointer"
          @click="$emit('changePage', (page || 1) - 1)"
        >
          上一页
        </button>

        <span class="font-semibold text-neutral-800">
          第 {{ page || 1 }} / {{ totalPages || 1 }} 页
        </span>

        <button
          type="button"
          :disabled="(page || 1) >= (totalPages || 1)"
          class="px-2.5 py-1 rounded-lg border border-neutral-200 bg-white font-medium text-neutral-700 hover:bg-neutral-100 disabled:opacity-40 disabled:hover:bg-white disabled:cursor-not-allowed transition-colors cursor-pointer"
          @click="$emit('changePage', (page || 1) + 1)"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  columns: string[]
  rows: (string | number)[][]
  rowCount: number
  totalCount?: number
  page?: number
  pageSize?: number
  totalPages?: number
  isTruncated?: boolean
}>()

defineEmits<{
  (e: 'changePage', page: number): void
  (e: 'changePageSize', size: number): void
}>()

const startRow = computed(() => {
  if (!props.totalCount || props.totalCount === 0) return 0
  const currentPage = props.page || 1
  const size = props.pageSize || 50
  return (currentPage - 1) * size + 1
})

const endRow = computed(() => {
  if (!props.totalCount || props.totalCount === 0) return 0
  const currentPage = props.page || 1
  const size = props.pageSize || 50
  return Math.min(currentPage * size, props.totalCount)
})
</script>
