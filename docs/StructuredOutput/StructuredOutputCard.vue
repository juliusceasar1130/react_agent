<!-- frontend/src/components/StructuredOutputCard.vue -->
<template>
  <div class="structured-output-card w-full rounded-2xl border border-neutral-200/80 bg-neutral-50/50 p-4 shadow-sm text-left text-neutral-800 text-[14px]">
    
    <!-- 格式一：StructuredDataResult (数据查询/报表模式) -->
    <div v-if="isStructuredData" class="space-y-4">
      
      <!-- 推理意图判断 -->
      <div v-if="data.judgment" class="flex items-center gap-2.5 rounded-xl bg-blue-50/80 px-4 py-2.5 text-xs font-semibold text-blue-700 border border-blue-100">
        <svg class="h-4 w-4 shrink-0 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
        <span>意图判定: {{ data.judgment }}</span>
      </div>

      <!-- 思考推理过程 Collapsible Details -->
      <div v-if="data.reasoning_process && data.reasoning_process.length" class="reasoning-section">
        <details class="group rounded-xl border border-neutral-200 bg-white p-3 transition-all duration-200">
          <summary class="flex cursor-pointer select-none items-center justify-between font-semibold text-neutral-700 hover:text-primary list-none">
            <span class="flex items-center gap-2 text-xs">
              <svg class="h-4 w-4 text-neutral-500 group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
              <span>查看 Agent 推理决策链路 ({{ data.reasoning_process.length }} 步)</span>
            </span>
            <svg class="h-3.5 w-3.5 text-neutral-400 transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          
          <div class="mt-3 space-y-3.5 border-t border-neutral-100 pt-3 pl-2">
            <div 
              v-for="step in data.reasoning_process" 
              :key="step.step" 
              class="relative border-l-2 border-neutral-200 pl-4 pb-2 last:pb-0"
            >
              <!-- Timeline Dot -->
              <span class="absolute -left-[7px] top-1.5 flex h-3 w-3 items-center justify-center rounded-full bg-neutral-300 ring-4 ring-white"></span>
              
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-xs font-bold text-neutral-700">步骤 {{ step.step }}</span>
                <span 
                  class="rounded-md px-1.5 py-0.5 text-[10px] font-bold"
                  :class="getConfidenceClass(step.confidence)"
                >
                  可信度: {{ step.confidence }}
                </span>
                <span 
                  v-if="step.user_should_verify" 
                  class="rounded-md bg-rose-50 border border-rose-100 px-1.5 py-0.5 text-[10px] font-bold text-rose-600"
                >
                  需人工验证
                </span>
              </div>
              <p class="mt-1 text-xs text-neutral-600 leading-relaxed font-medium">
                {{ step.thought }}
              </p>
              <p v-if="step.suggestion" class="mt-1 text-xs text-rose-600 font-semibold pl-1 border-l border-rose-200">
                <strong>建议:</strong> {{ step.suggestion }}
              </p>
            </div>
          </div>
        </details>
      </div>

      <!-- 高度定制的表格 Table Card -->
      <div 
        v-for="(table, tIdx) in data.tables" 
        :key="tIdx" 
        class="rounded-xl border border-neutral-200 bg-white p-3.5 shadow-sm"
      >
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-neutral-100 pb-2.5">
          <h4 class="font-bold text-neutral-800 text-[14px]">
            {{ table.title || '结果数据表' }}
          </h4>
          <button 
            type="button" 
            class="flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-2.5 py-1 text-xs font-semibold text-neutral-600 transition hover:bg-neutral-50 hover:text-primary active:scale-95 shadow-sm self-start sm:self-auto"
            @click="exportToExcel(table)"
          >
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>导出 CSV</span>
          </button>
        </div>

        <!-- 斑马纹带排序功能的前端表格 -->
        <div class="mt-3 overflow-x-auto rounded-lg border border-neutral-200">
          <table class="min-w-full divide-y divide-neutral-200 text-left text-xs font-medium text-neutral-600">
            <thead class="bg-neutral-50">
              <tr>
                <th 
                  v-for="col in table.headers" 
                  :key="col"
                  scope="col"
                  class="cursor-pointer select-none px-4 py-3 text-[11px] font-bold text-neutral-500 hover:bg-neutral-100/80 transition-colors uppercase tracking-wider whitespace-nowrap"
                  @click="toggleSort(col)"
                >
                  <div class="flex items-center gap-1.5">
                    <span>{{ col }}</span>
                    <!-- 排序指示器 -->
                    <span class="flex flex-col text-[8px] text-neutral-400">
                      <span :class="sortCol === col && sortDir === 1 ? 'text-primary' : ''">▲</span>
                      <span :class="sortCol === col && sortDir === -1 ? 'text-primary' : ''">▼</span>
                    </span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-neutral-200 bg-white">
              <tr 
                v-for="(row, rIdx) in getSortedRows(table)" 
                :key="rIdx"
                class="hover:bg-neutral-50/50 transition-colors odd:bg-white even:bg-neutral-50/30"
              >
                <td 
                  v-for="(cell, cIdx) in row" 
                  :key="cIdx" 
                  class="px-4 py-2.5 max-w-[260px] truncate font-medium text-neutral-700"
                  :title="String(cell ?? '')"
                >
                  {{ cell ?? '-' }}
                </td>
              </tr>
              <tr v-if="!table.rows || !table.rows.length">
                <td :colspan="table.headers.length" class="px-4 py-8 text-center text-neutral-400">
                  没有查询到相关数据
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 智能洞察与结论 Insights -->
      <div v-if="data.insights && data.insights.length" class="rounded-xl border border-amber-200 bg-amber-50/50 p-3.5 shadow-sm space-y-2">
        <div class="flex items-center gap-2 text-amber-800 font-bold text-xs">
          <svg class="h-4 w-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span>数据分析洞察与核心结论</span>
        </div>
        <ul class="space-y-1.5 pl-1.5">
          <li v-for="(insight, insIdx) in data.insights" :key="insIdx" class="flex items-start gap-2 text-xs text-neutral-600 font-medium">
            <span class="text-amber-500 font-bold">•</span>
            <span>{{ insight }}</span>
          </li>
        </ul>
      </div>

    </div>

    <!-- 格式二：FreeMarkdownResult (开放式问答模式) -->
    <div v-else-if="isFreeMarkdown" class="space-y-4">
      
      <!-- 响应类型标签 -->
      <div class="response-type-header flex">
        <span 
          class="rounded-md px-2 py-0.5 text-[10px] font-bold border"
          :class="getMarkdownTagClass(data.response_type)"
        >
          {{ getMarkdownTagLabel(data.response_type) }}
        </span>
      </div>

      <!-- Markdown 渲染主体 -->
      <div class="markdown-body-render text-left leading-relaxed" v-html="parsedMarkdown" />

      <!-- 联想建议表 & 提问 -->
      <div v-if="hasSuggestions" class="mt-4 pt-3 border-t border-neutral-200/50 space-y-3">
        
        <!-- 相关数据表 -->
        <div v-if="data.suggested_tables && data.suggested_tables.length" class="flex flex-wrap items-center gap-1.5">
          <span class="text-xs font-semibold text-neutral-500">建议查询表：</span>
          <span 
            v-for="tab in data.suggested_tables" 
            :key="tab" 
            class="cursor-pointer rounded-full bg-neutral-200/60 px-2.5 py-0.5 text-xs text-neutral-600 transition hover:bg-primary/10 hover:text-primary active:scale-95 font-medium"
            @click="onSuggestClick(tab)"
          >
            {{ tab }}
          </span>
        </div>

        <!-- 联想问法 -->
        <div v-if="data.suggested_questions && data.suggested_questions.length" class="space-y-2">
          <div class="text-xs font-semibold text-neutral-500">您可能还想问：</div>
          <div class="flex flex-col gap-2 items-start">
            <button 
              v-for="q in data.suggested_questions" 
              :key="q" 
              type="button"
              class="rounded-2xl border border-neutral-200 bg-white px-3 py-1.5 text-xs font-medium text-blue-600 transition hover:bg-blue-50 hover:border-blue-300 active:scale-95 text-left shadow-sm hover:shadow"
              @click="onQuestionClick(q)"
            >
              💡 {{ q }}
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  data: any
}>()

const emit = defineEmits<{
  (e: 'send-message', text: string): void
}>()

// 表格排序状态
const sortCol = ref('')
const sortDir = ref(0) // 0: 不排序, 1: 升序, -1: 降序

const isStructuredData = computed(() => {
  return props.data && Array.isArray(props.data.tables)
})

const isFreeMarkdown = computed(() => {
  return props.data && props.data.content !== undefined
})

const hasSuggestions = computed(() => {
  return props.data && (
    (props.data.suggested_tables && props.data.suggested_tables.length) ||
    (props.data.suggested_questions && props.data.suggested_questions.length)
  )
})

const parsedMarkdown = computed(() => {
  return renderMarkdown(props.data?.content || '')
})

// 处理排序切换
const toggleSort = (colName: string) => {
  if (sortCol.value !== colName) {
    sortCol.value = colName
    sortDir.value = 1
  } else if (sortDir.value === 1) {
    sortDir.value = -1
  } else {
    sortCol.value = ''
    sortDir.value = 0
  }
}

// 获取排序后的行矩阵
const getSortedRows = (table: any) => {
  if (!table.rows || !table.rows.length) return []
  if (!sortCol.value || sortDir.value === 0) return table.rows

  // 找到当前排序列在 headers 里的索引位置
  const colIdx = table.headers.indexOf(sortCol.value)
  if (colIdx === -1) return table.rows

  // 浅拷贝并执行排序
  const rowsCopy = [...table.rows]
  rowsCopy.sort((a, b) => {
    const valA = a[colIdx]
    const valB = b[colIdx]

    if (valA === valB) return 0
    if (valA === null || valA === undefined) return 1
    if (valB === null || valB === undefined) return -1

    const numA = Number(valA)
    const numB = Number(valB)

    if (!isNaN(numA) && !isNaN(numB)) {
      return (numA - numB) * sortDir.value
    }

    return String(valA).localeCompare(String(valB)) * sortDir.value
  })

  return rowsCopy
}

// 根据可信度级别返回颜色样式
const getConfidenceClass = (confidence: string) => {
  switch (confidence) {
    case 'high': return 'bg-emerald-50 text-emerald-700 border border-emerald-100'
    case 'medium': return 'bg-amber-50 text-amber-700 border border-amber-100'
    case 'low': return 'bg-rose-50 text-rose-700 border border-rose-100'
    default: return 'bg-neutral-50 text-neutral-500 border border-neutral-100'
  }
}

// 根据回复流分类获取样式
const getMarkdownTagClass = (type: string) => {
  switch (type) {
    case 'explanation': return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    case 'clarification': return 'bg-amber-50 text-amber-700 border-amber-200'
    case 'refusal': return 'bg-rose-50 text-rose-700 border-rose-200'
    default: return 'bg-neutral-50 text-neutral-500 border-neutral-200'
  }
}

const getMarkdownTagLabel = (type: string) => {
  switch (type) {
    case 'explanation': return '解释说明'
    case 'clarification': return '意图澄清'
    case 'refusal': return '拒绝执行'
    default: return '自由回复'
  }
}

// 发送用户点击的建议或问题
const onQuestionClick = (question: string) => {
  emit('send-message', question)
}

const onSuggestClick = (table: string) => {
  emit('send-message', `查一下表 ${table}`)
}

// 导出 CSV 文件（支持带 UTF-8 BOM 中文无缝打开）
const exportToExcel = (table: any) => {
  let csvContent = '\uFEFF' + table.headers.join(',') + '\n'
  table.rows.forEach((row: any[]) => {
    csvContent += row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',') + '\n'
  })
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.setAttribute('download', `${table.title || 'report_export'}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>

<style scoped>
.structured-output-card :deep(.markdown-body) {
  font-size: 14px;
  line-height: 1.625;
  color: #374151;
}
.structured-output-card :deep(.markdown-body p) {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}
.structured-output-card :deep(.markdown-body pre) {
  background-color: #f3f4f6;
  border-radius: 8px;
  padding: 10px 14px;
  margin: 8px 0;
  overflow-x: auto;
}
.structured-output-card :deep(.markdown-body code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  background-color: #f3f4f6;
  padding: 2px 4px;
  border-radius: 4px;
}
.structured-output-card :deep(.markdown-body ul) {
  list-style-type: disc;
  padding-left: 1.25rem;
  margin: 6px 0;
}
.structured-output-card :deep(.markdown-body ol) {
  list-style-type: decimal;
  padding-left: 1.25rem;
  margin: 6px 0;
}
</style>
