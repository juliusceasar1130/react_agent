<!-- 2026-08-20 - 子智能体独立卡片组件：支持独立思考、工具链调用、专属工件内嵌与状态展示 -->
<template>
  <div
    class="my-3 overflow-hidden rounded-xl border transition-all duration-200"
    :class="cardBorderClass"
  >
    <!-- 卡片头部 -->
    <div
      class="flex cursor-pointer items-center justify-between px-3.5 py-2.5 select-none transition-colors"
      :class="headerBgClass"
      @click="toggleExpand"
    >
      <div class="flex items-center gap-2">
        <!-- 智能体图标 -->
        <div class="flex h-6 w-6 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>

        <!-- 智能体名称 -->
        <span class="text-xs font-semibold text-neutral-800 dark:text-neutral-200">
          {{ subagent.title || formatSubagentName(subagent.name) }}
        </span>

        <!-- 状态标签 -->
        <span
          class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium"
          :class="statusBadgeClass"
        >
          <span v-if="isAwaitingClarification" class="relative flex h-1.5 w-1.5">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-75"></span>
            <span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-500"></span>
          </span>
          <span v-else-if="subagent.status === 'running'" class="relative flex h-1.5 w-1.5">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
            <span class="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary"></span>
          </span>
          <svg v-else-if="subagent.status === 'completed'" class="h-3 w-3 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else-if="subagent.status === 'interrupted'" class="h-3 w-3 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <svg v-else-if="subagent.status === 'error'" class="h-3 w-3 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          {{ statusText }}
        </span>

        <!-- 耗时 -->
        <span v-if="durationDisplay" class="text-[11px] text-neutral-400 font-mono">
          ({{ durationDisplay }})
        </span>
      </div>

      <!-- 折叠展开按钮 -->
      <div class="flex items-center gap-1.5 text-neutral-400">
        <span class="text-[11px] font-normal text-neutral-400">{{ isExpanded ? '收起' : '展开详情' }}</span>
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
    </div>

    <!-- 卡片展开主体 -->
    <div v-show="isExpanded" class="border-t border-neutral-200/60 bg-white/60 px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900/60">
      <!-- 1. 独立思考折叠区域 -->
      <div v-if="subagent.reasoningText" class="mb-3">
        <ReasoningAccordion
          :reasoning-text="subagent.reasoningText"
          :is-streaming="subagent.status === 'running'"
          :duration="subagent.reasoningDuration"
        />
      </div>

      <!-- 2. 工具调用过程链 (支持富工件就近内嵌) -->
      <div v-if="subagent.toolCalls && subagent.toolCalls.length > 0" class="mb-3 space-y-2.5">
        <div class="text-[11px] font-semibold tracking-wider text-neutral-500 uppercase">工具调用序列</div>
        <div
          v-for="tool in subagent.toolCalls"
          :key="tool.id"
          class="rounded-lg border border-neutral-200/70 bg-neutral-50/70 p-2.5 text-xs transition-colors dark:border-neutral-800 dark:bg-neutral-800/40"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-1.5 font-medium text-neutral-700 dark:text-neutral-200">
              <span class="rounded bg-primary/10 px-1.5 py-0.5 text-[11px] font-mono text-primary">{{ tool.name }}</span>
            </div>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-medium"
              :class="tool.status === 'completed' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400' : (tool.name === 'AskUserQuestion' ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400' : 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400')"
            >
              {{ tool.status === 'completed' ? (tool.name === 'AskUserQuestion' ? '已确认' : '已完成') : (tool.name === 'AskUserQuestion' ? '等待用户确认...' : '执行中...') }}
            </span>
          </div>

          <!-- 工具输入参数 -->
          <div v-if="tool.args_text" class="mt-2">
            <div class="text-[10px] text-neutral-400">调用参数:</div>
            <pre class="mt-0.5 max-h-32 overflow-auto rounded bg-neutral-100/80 p-1.5 font-mono text-[11px] text-neutral-600 dark:bg-neutral-900/80 dark:text-neutral-300">{{ tool.args_text }}</pre>
          </div>

          <!-- 终态工件 A: 内嵌 SQL 数据结果表格 (支持 20/50/100 分页与截断提示) -->
          <div v-if="getToolQueryResult(tool.id)" class="mt-2.5 text-left animate-fade-in">
            <QueryResultGroup :tables="[getToolQueryResult(tool.id)!]" />
          </div>

          <!-- 终态工件 B: 轻量 CSV 交付胶囊 (避免重复渲染全量卡片) -->
          <div v-else-if="getToolCsvExport(tool.id)" class="mt-2 flex items-center justify-between rounded-lg bg-emerald-50/60 border border-emerald-200/60 px-2.5 py-1.5 text-xs text-emerald-800 dark:bg-emerald-950/30 dark:border-emerald-900/40 dark:text-emerald-300">
            <div class="flex items-center gap-1.5 truncate">
              <span>📄</span>
              <span class="font-medium truncate">{{ getToolCsvExport(tool.id)!.filename }}</span>
              <span class="text-[11px] text-emerald-600/80 dark:text-emerald-400/80 font-mono">({{ getToolCsvExport(tool.id)!.row_count }} 行)</span>
            </div>
            <span class="text-[10px] text-neutral-400 shrink-0 ml-2">已交付至主视口</span>
          </div>

          <!-- 终态工件 C: 轻量图表交付胶囊 (避免双重 Canvas 实例) -->
          <div v-else-if="getToolChartArtifact(tool.id)" class="mt-2 flex items-center justify-between rounded-lg bg-primary/5 border border-primary/20 px-2.5 py-1.5 text-xs text-primary dark:bg-primary/10 dark:border-primary/30">
            <div class="flex items-center gap-1.5 truncate">
              <span>📊</span>
              <span class="font-medium truncate">{{ getToolChartArtifact(tool.id)!.title || '数据图表' }}</span>
            </div>
            <span class="text-[10px] text-neutral-400 shrink-0 ml-2">已交付至主视口</span>
          </div>

          <!-- 过程知识/文本工具输出结果 (轻量折叠) -->
          <div v-else-if="subagent.toolResults && subagent.toolResults[tool.id]" class="mt-2">
            <details class="group">
              <summary class="cursor-pointer text-[10px] text-neutral-400 hover:text-neutral-600 select-none">
                查看执行结果 <span class="group-open:inline hidden">▲</span><span class="group-open:hidden inline">▼</span>
              </summary>
              <pre class="mt-1 max-h-40 overflow-auto rounded bg-neutral-100/80 p-1.5 font-mono text-[11px] text-neutral-600 dark:bg-neutral-900/80 dark:text-neutral-300">{{ subagent.toolResults[tool.id] }}</pre>
            </details>
          </div>
        </div>
      </div>

      <!-- 等待用户确认参数的引导 Banner 与平滑滚动按钮 -->
      <div v-if="isAwaitingClarification" class="my-2.5 flex items-center justify-between gap-3 rounded-lg border border-blue-200/80 bg-blue-50/60 p-2.5 px-3 dark:border-blue-900/60 dark:bg-blue-950/30 animate-fade-in">
        <div class="flex items-center gap-2 text-xs font-medium text-blue-800 dark:text-blue-200">
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-75"></span>
            <span class="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
          </span>
          <span>正在等待您在下方卡片中确认参数...</span>
        </div>
        <button
          type="button"
          @click.stop="scrollToClarificationCard"
          class="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-[11px] font-semibold text-white shadow-xs hover:bg-blue-700 active:scale-95 transition-all"
        >
          <span>定位到表单</span>
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      </div>

      <!-- 3. 子智能体产出内容 (Markdown) -->
      <div v-if="subagent.content" class="mt-2 border-t border-neutral-100 pt-2 dark:border-neutral-800">
        <div class="text-[11px] font-semibold tracking-wider text-neutral-500 uppercase mb-1">执行总结</div>
        <div class="message-markdown text-xs leading-relaxed text-neutral-700 dark:text-neutral-200" v-html="renderedSubagentContent"></div>
      </div>

      <!-- 4. 错误信息展示 -->
      <div v-if="subagent.error" class="mt-2 rounded-lg border border-red-200 bg-red-50/70 p-2 text-xs text-red-600 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-400">
        {{ subagent.error }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { SubagentSessionState } from '@/types'
import { renderMarkdown } from '@/utils/markdown'
import { formatSubagentTitle } from '@/utils/helpers'
import ReasoningAccordion from './ReasoningAccordion.vue'
import QueryResultGroup from '@/components/artifacts/QueryResultGroup.vue'

const props = defineProps<{
  subagent: SubagentSessionState
  artifactsPool?: Record<string, any>
}>()

// 解析对应工具产出的结构化工件实体
const getToolArtifact = (toolId: string): any => {
  if (!props.artifactsPool) return null
  return props.artifactsPool[toolId] || null
}

const getParsedToolResult = (toolId: string): any => {
  const raw = props.subagent.toolResults?.[toolId]
  if (!raw || typeof raw !== 'string') return null
  try {
    const trimmed = raw.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      return JSON.parse(trimmed)
    }
  } catch {
    return null
  }
  return null
}

// 提取并归一化 SQL 数据表工件
const getToolQueryResult = (toolId: string) => {
  const normalize = (item: any) => {
    if (!item) return null
    return {
      ...item,
      is_truncated: Boolean(item.is_truncated ?? item.truncated),
      row_count: item.row_count ?? item.total_count ?? item.rows?.length ?? 0,
      total_count: item.total_count ?? item.row_count ?? item.rows?.length ?? 0,
    }
  }

  const art = getToolArtifact(toolId)
  if (art && art.kind === 'query_result' && Array.isArray(art.rows)) {
    return normalize(art)
  }
  const parsed = getParsedToolResult(toolId)
  if (parsed && parsed.kind === 'query_result' && Array.isArray(parsed.rows)) {
    return normalize(parsed)
  }
  return null
}

// 提取 CSV 导出工件
const getToolCsvExport = (toolId: string) => {
  const art = getToolArtifact(toolId)
  if (art && (art.kind === 'file_export' || art.file_id || art.artifact_id)) {
    return {
      file_id: art.file_id || art.artifact_id,
      filename: art.filename || art.extra?.filename || `${art.artifact_id || 'export'}.csv`,
      row_count: art.row_count ?? 0,
      col_count: art.col_count ?? (Array.isArray(art.columns) ? art.columns.length : 0),
      size_bytes: art.size_bytes || art.extra?.size_bytes,
      expires_at: art.expires_at || '',
    }
  }
  const parsed = getParsedToolResult(toolId)
  if (parsed && (parsed.kind === 'file_export' || parsed.kind === 'export_file_ref' || parsed.file_id)) {
    return {
      file_id: parsed.file_id || parsed.artifact_id,
      filename: parsed.filename || `${parsed.file_id || 'export'}.csv`,
      row_count: parsed.row_count ?? 0,
      col_count: parsed.col_count ?? 0,
      size_bytes: parsed.size_bytes,
      expires_at: parsed.expires_at || '',
    }
  }
  return null
}

// 提取图表工件
const getToolChartArtifact = (toolId: string) => {
  const art = getToolArtifact(toolId)
  if (art && (art.kind === 'chart_spec' || art.kind === 'chart_artifact_ref')) {
    return art
  }
  const parsed = getParsedToolResult(toolId)
  if (parsed && (parsed.kind === 'chart_spec' || parsed.kind === 'chart_artifact_ref' || parsed.chart_id)) {
    return parsed
  }
  return null
}

const isAwaitingClarification = computed(() => {
  if (props.subagent.status !== 'running') {
    return false
  }
  return !!props.subagent.toolCalls?.some(
    t => t.name === 'AskUserQuestion' && t.status !== 'completed'
  )
})

const isExpanded = ref(props.subagent.status === 'running' || isAwaitingClarification.value)
const isUserToggled = ref(false)

const toggleExpand = () => {
  isUserToggled.value = true
  isExpanded.value = !isExpanded.value
}

watch(
  () => [props.subagent.status, isAwaitingClarification.value],
  ([newStatus, awaiting]) => {
    if (!isUserToggled.value) {
      if (newStatus === 'running' || awaiting) {
        isExpanded.value = true
      }
    }
  }
)

// 复用统一渲染工具链（MarkdownIt html:false + DOMPurify 清洗，见 utils/markdown.ts）
const renderedSubagentContent = computed(() => {
  if (!props.subagent.content) return ''
  return renderMarkdown(props.subagent.content)
})

// 复用统一命名映射（utils/helpers.ts），与 messages store 保持一致
const formatSubagentName = (name: string) => formatSubagentTitle(name)

const statusText = computed(() => {
  if (isAwaitingClarification.value) {
    return '等待确认'
  }
  switch (props.subagent.status) {
    case 'running':
      return '执行中...'
    case 'completed':
      return '已完成'
    case 'interrupted':
      return '已中断'
    case 'error':
      return '执行失败'
    default:
      return '已就绪'
  }
})

const statusBadgeClass = computed(() => {
  if (isAwaitingClarification.value) {
    return 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-200/50'
  }
  switch (props.subagent.status) {
    case 'running':
      return 'bg-primary/10 text-primary'
    case 'completed':
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
    case 'interrupted':
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
    case 'error':
      return 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300'
    default:
      return 'bg-neutral-100 text-neutral-600'
  }
})

const cardBorderClass = computed(() => {
  if (isAwaitingClarification.value) {
    return 'border-blue-200/90 dark:border-blue-900/40 bg-blue-50/[0.03] shadow-xs'
  }
  switch (props.subagent.status) {
    case 'running':
      return 'border-primary/30 bg-primary/[0.02] shadow-xs'
    case 'error':
      return 'border-red-200 dark:border-red-900/40 bg-red-50/[0.02]'
    case 'interrupted':
      return 'border-amber-200 dark:border-amber-900/40 bg-amber-50/[0.02]'
    default:
      return 'border-neutral-200/70 dark:border-neutral-800 bg-neutral-50/40'
  }
})

const headerBgClass = computed(() => {
  switch (props.subagent.status) {
    case 'running':
      return 'bg-primary/[0.04] hover:bg-primary/[0.08]'
    default:
      return 'hover:bg-neutral-100/60 dark:hover:bg-neutral-800/60'
  }
})

const durationDisplay = computed(() => {
  if (props.subagent.reasoningDuration !== undefined && props.subagent.reasoningDuration > 0) {
    return `${props.subagent.reasoningDuration.toFixed(1)}s`
  }
  return ''
})

const scrollToClarificationCard = () => {
  const target = document.querySelector('textarea, input[type="text"]') || document.querySelector('.animate-fade-in')
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
      target.focus()
    }
  }
}
</script>
