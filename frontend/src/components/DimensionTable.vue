<template>
  <div class="mx-auto w-full max-w-5xl px-3 py-6 sm:px-5 lg:px-6">
    <!-- 头部卡片 -->
    <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div class="flex items-center gap-2">
          <h2 class="text-xl font-bold text-neutral-800 tracking-tight">{{ title }}</h2>
        </div>
        <p class="mt-1 text-xs text-neutral-500 font-mono">
          表名: {{ tableName }} · 共 {{ rows.length }} 行记录
        </p>
      </div>

      <!-- 复制表名动作按钮 -->
      <div class="flex items-center gap-2">
        <button
          @click="copyText(tableName, 'table')"
          class="inline-flex items-center gap-1.5 rounded-xl border border-neutral-200 bg-white px-3 py-2 text-xs font-medium text-neutral-600 shadow-sm transition hover:bg-neutral-50 hover:text-neutral-800 active:scale-98"
        >
          <svg
            v-if="copiedType === 'table'"
            class="h-3.5 w-3.5 text-emerald-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
            />
          </svg>
          {{ copiedType === 'table' ? '表名已复制' : '复制表名' }}
        </button>
      </div>
    </div>

    <!-- 表格卡片主体 -->
    <div v-if="rows.length === 0" class="panel rounded-3xl p-12 text-center text-sm text-neutral-400">
      该表暂无数据
    </div>

    <div
      v-else
      class="relative overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm transition-all duration-300 hover:shadow-md"
    >
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm border-collapse">
          <thead>
            <tr class="border-b border-neutral-200 bg-neutral-50/70">
              <th
                v-for="col in filteredColumns"
                :key="col"
                class="px-4 py-3 font-semibold text-neutral-600 tracking-tight whitespace-nowrap cursor-pointer select-none"
                @dblclick="$emit('dblclick-cell', col)"
                title="双击可自动注入输入框"
              >
                <div class="flex items-center gap-1">
                  <span>{{ col }}</span>
                  <!-- 点击复制列名 -->
                  <button
                    @click="copyText(col, 'column-' + col)"
                    class="rounded p-0.5 text-neutral-400 hover:bg-neutral-200/60 hover:text-neutral-700 transition"
                    title="复制字段名"
                  >
                    <svg
                      v-if="copiedType === 'column-' + col"
                      class="h-3 w-3 text-emerald-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                    </svg>
                    <svg v-else class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="1.8"
                        d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                      />
                    </svg>
                  </button>
                </div>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-neutral-100">
            <tr
              v-for="(row, ri) in filteredRows"
              :key="ri"
              class="group hover:bg-neutral-50/50 transition-colors"
            >
              <td
                v-for="(cell, ci) in row"
                :key="ci"
                class="relative px-4 py-3 text-neutral-700 font-mono text-xs whitespace-nowrap cursor-pointer select-none"
                @dblclick="$emit('dblclick-cell', String(cell))"
                title="双击可自动注入输入框"
              >
                <div class="flex items-center justify-between gap-3">
                  <span>{{ cell === null || cell === undefined ? 'NULL' : cell }}</span>
                  <!-- 点击复制单元格值 -->
                  <button
                    v-if="showCellCopy(filteredColumns[ci])"
                    @click="copyText(String(cell), 'cell-' + ri + '-' + ci)"
                    class="rounded p-0.5 text-neutral-400 hover:bg-neutral-200/70 hover:text-neutral-600 transition"
                    title="复制单元格内容"
                  >
                    <svg
                      v-if="copiedType === 'cell-' + ri + '-' + ci"
                      class="h-3.5 w-3.5 text-emerald-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                    </svg>
                    <svg v-else class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="1.8"
                        d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"
                      />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 浮动复制反馈 Mini Toast -->
    <Transition name="fade">
      <div
        v-if="showToast"
        class="fixed right-6 top-6 z-[99999] flex items-center gap-1.5 rounded-2xl bg-neutral-900 px-4 py-2.5 text-xs font-medium text-white shadow-xl"
      >
        <span class="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
        </span>
        已成功复制到剪贴板！
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  title: string
  tableName: string
  columns: string[]
  rows: (string | number)[][]
}>()

const emit = defineEmits<{
  'dblclick-cell': [value: string]
}>()

const copiedType = ref<string | null>(null)
const showToast = ref(false)
let toastTimer: any = null

const _TIME_PATTERNS = /date|time|_at|seen/i

// 过滤掉时间相关的列
const filteredColumns = computed(() => {
  return props.columns.filter(col => !_TIME_PATTERNS.test(col))
})

// 过滤每一行对应的数据单元格
const filteredRows = computed(() => {
  const activeIndices = props.columns
    .map((col, index) => ({ col, index }))
    .filter(item => !_TIME_PATTERNS.test(item.col))
    .map(item => item.index)

  return props.rows.map(row => {
    return activeIndices.map(index => row[index])
  })
})

function showCellCopy(colName: string): boolean {
  return !_TIME_PATTERNS.test(colName)
}

async function copyText(text: string, type: string) {
  try {
    await navigator.clipboard.writeText(text)
    copiedType.value = type
    showToast.value = true
    
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      copiedType.value = null
      showToast.value = false
    }, 1500)
  } catch (err) {
    console.error('无法复制内容:', err)
  }
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
