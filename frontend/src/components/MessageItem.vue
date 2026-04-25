<!-- 2026-04-19 23:40 Asia/Shanghai - 消息气泡更新：统一卡片层级与现代阅读体验 -->
<template>
  <div
    class="flex animate-slide-up"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="w-full max-w-[92%] rounded-[24px] shadow-sm transition-all duration-200 sm:max-w-[88%]"
      :class="messageWrapperClass"
    >
      <div
        v-if="isInterruptedMessage && !isUser"
        class="px-5 pt-3 text-xs font-medium tracking-wide text-amber-700"
      >
        已停止生成
      </div>

      <div
        v-if="showDebugDetails && statusText && !isUser"
        class="px-5 pt-3 text-xs font-medium tracking-wide"
        :class="statusClass"
      >
        {{ statusText }}
      </div>

      <div class="px-5 py-3.5">
        <p
          v-if="isUser || isStreamingActive"
          class="whitespace-pre-wrap break-words text-[15px] leading-7"
          :class="textClass"
        >
          <template v-if="isStreamingActive">
            {{ content }}
            <span class="cursor-blink"></span>
          </template>
          <template v-else>
            {{ content }}
          </template>
        </p>
        <div
          v-else
          class="message-markdown break-words text-[15px] leading-relaxed"
          :class="textClass"
          v-html="renderedContent"
        ></div>
      </div>

      <div
        v-if="!isUser && exportArtifacts.length > 0"
        class="space-y-3 px-4 pb-3"
      >
        <div
          v-for="artifact in exportArtifacts"
          :key="artifact.file_id"
          class="rounded-[22px] border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-emerald-50/50 px-4 py-3 shadow-sm"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-emerald-800">CSV 文件已生成</div>
              <div class="mt-1 break-all text-sm text-emerald-700">{{ artifact.filename }}</div>
              <div class="mt-2 text-xs leading-5 text-emerald-700/90">
                <span v-if="artifact.row_count !== undefined && artifact.col_count !== undefined">
                  {{ artifact.row_count }} 行 × {{ artifact.col_count }} 列
                </span>
                <span v-if="artifact.size_bytes !== undefined">
                  · {{ formatFileSize(artifact.size_bytes) }}
                </span>
              </div>
              <div
                v-if="artifact.columns && artifact.columns.length > 0"
                class="mt-1 text-xs leading-5 text-emerald-700/90"
              >
                列名：{{ artifact.columns.join('、') }}
              </div>
              <div
                v-if="artifact.expires_at"
                class="mt-1 text-xs leading-5 text-emerald-700/80"
              >
                有效期至：{{ formatDateTime(artifact.expires_at) }}
              </div>
            </div>

            <button
              type="button"
              class="shrink-0 rounded-2xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700"
              @click="handleExportDownload(artifact.file_id)"
            >
              下载 CSV
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="!isUser && chartArtifacts.length > 0"
        class="space-y-3 px-4 pb-3"
      >
        <ChartArtifactCard
          v-for="artifact in chartArtifacts"
          :key="artifact.chart_id"
          :artifact-ref="artifact"
        />
      </div>

      <div
        v-if="showDebugDetails && !isUser && toolCallList.length > 0"
        class="space-y-2 px-4 pb-3"
      >
        <div
          v-for="tool in toolCallList"
          :key="tool.id"
          class="rounded-2xl border border-primary/15 bg-white/70 px-3 py-2 text-xs text-neutral-600"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="font-medium text-primary">{{ tool.name }}</span>
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
              {{ toolStatusText(tool) }}
            </span>
          </div>
          <p v-if="tool.args_text" class="mt-1 max-h-24 overflow-hidden whitespace-pre-wrap break-all text-neutral-500">
            {{ tool.args_text }}
          </p>
        </div>
      </div>

      <div
        v-if="showDebugDetails && !isUser && toolResultEntries.length > 0"
        class="space-y-2 px-4 pb-3"
      >
        <details
          v-for="toolResult in toolResultEntries"
          :key="toolResult.id"
          class="rounded-2xl border border-neutral-200 bg-surface/90 px-3 py-2 text-xs text-neutral-600"
        >
          <summary class="cursor-pointer select-none font-medium text-neutral-700">
            工具结果 {{ toolResult.id }}
          </summary>
          <pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-relaxed text-neutral-500">{{ toolResult.content }}</pre>
        </details>
      </div>

      <div
        v-if="showDebugDetails && errorText && !isUser"
        class="px-4 pb-3"
      >
        <div class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
          {{ errorText }}
        </div>
      </div>

      <div
        class="flex items-center justify-end gap-1.5 px-4 pb-2.5 pt-0"
        :class="timeClass"
      >
        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-xs">{{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ChartArtifactCard from '@/components/ChartArtifactCard.vue'
import { triggerExportDownload } from '@/api/exports'
import { CHAT_DEBUG_STREAM } from '@/config/chat'
import type {
  ChartArtifactRef,
  ExportArtifact,
  Message,
  StreamToolCall,
  StreamingMessage
} from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'
import { renderMarkdown } from '@/utils/markdown'

interface Props {
  message: Message | StreamingMessage
}

interface ToolResultEntry {
  id: string
  content: string
}

const props = defineProps<Props>()

const { formatTime, parseServerDate } = useDateFormat()

const parseJson = <T,>(value?: string | null): T | null => {
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

const isUser = computed(() => props.message.role === 'user')

const streamingState = computed<StreamingMessage | null>(() => {
  if ('toolCalls' in props.message && 'toolResults' in props.message) {
    return props.message as StreamingMessage
  }
  return null
})

const isStreamingActive = computed(() => Boolean(streamingState.value?.isStreaming))
const showDebugDetails = CHAT_DEBUG_STREAM

const content = computed(() =>
  streamingState.value ? streamingState.value.content : props.message.content
)
const renderedContent = computed(() => renderMarkdown(content.value))

const rawToolResults = computed<Record<string, string>>(() => {
  const message = props.message as Message
  return streamingState.value?.toolResults ?? parseJson<Record<string, string>>(message.tool_results) ?? {}
})

const statusText = computed(() => streamingState.value?.statusText ?? null)
const errorText = computed(() => streamingState.value?.error ?? null)
const isInterruptedMessage = computed(() => {
  if (streamingState.value) {
    return Boolean(streamingState.value.isInterrupted)
  }
  return Boolean((props.message as Message).is_interrupted)
})

const toolCallList = computed<StreamToolCall[]>(() => {
  if (streamingState.value) {
    return streamingState.value.toolCalls
  }

  const message = props.message as Message
  const parsed = parseJson<StreamToolCall[]>(message.tool_calls)
  return Array.isArray(parsed) ? parsed : []
})

const toolResultEntries = computed<ToolResultEntry[]>(() => {
  return Object.entries(rawToolResults.value).map(([id, result]) => ({
    id,
    content: String(result)
  }))
})

const isExportArtifact = (value: unknown): value is ExportArtifact => {
  if (!value || typeof value !== 'object') return false
  const artifact = value as Record<string, unknown>
  return (
    artifact.kind === 'file_export'
    && typeof artifact.file_id === 'string'
    && typeof artifact.filename === 'string'
  )
}

const exportArtifacts = computed<ExportArtifact[]>(() => {
  const results = rawToolResults.value

  return toolCallList.value.flatMap((tool) => {
    if (tool.name !== 'export_to_csv') {
      return []
    }

    const rawResult = results[tool.id]
    if (typeof rawResult !== 'string') {
      return []
    }

    const parsed = parseJson<ExportArtifact>(rawResult)
    if (!isExportArtifact(parsed)) {
      return []
    }

    return [parsed]
  })
})

const isChartArtifactRef = (value: unknown): value is ChartArtifactRef => {
  if (!value || typeof value !== 'object') return false
  const artifact = value as Record<string, unknown>
  return (
    artifact.kind === 'chart_artifact_ref'
    && typeof artifact.chart_id === 'string'
    && typeof artifact.title === 'string'
  )
}

const chartArtifacts = computed<ChartArtifactRef[]>(() => {
  const results = rawToolResults.value

  return toolCallList.value.flatMap((tool) => {
    if (tool.name !== 'build_chart_artifact') {
      return []
    }

    const rawResult = results[tool.id]
    if (typeof rawResult !== 'string') {
      return []
    }

    const parsed = parseJson<ChartArtifactRef>(rawResult)
    if (!isChartArtifactRef(parsed)) {
      return []
    }

    return [parsed]
  })
})

const hasToolResult = (toolId: string) => toolResultEntries.value.some(item => item.id === toolId)

const formatFileSize = (sizeBytes: number) => {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`
  }
  return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
}

const formatDateTime = (value: string) => {
  const date = parseServerDate(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

const handleExportDownload = (fileId: string) => {
  triggerExportDownload(fileId)
}

const toolStatusText = (tool: StreamToolCall) => {
  if (tool.status === 'completed' || hasToolResult(tool.id)) {
    return '已完成'
  }

  if (isInterruptedMessage.value) {
    return '已停止'
  }

  const status = tool.status
  switch (status) {
    case 'started':
      return '已开始'
    default:
      return '执行中'
  }
}

const messageWrapperClass = computed(() => {
  if (isUser.value) {
    return 'border border-[#B8D7F3] bg-[#DBECFF] shadow-sm'
  }
  if (errorText.value) {
    return 'border border-red-200 bg-gradient-to-br from-red-50 to-white'
  }
  if (isInterruptedMessage.value) {
    return 'border border-amber-200 bg-gradient-to-br from-amber-50 to-white'
  }
  if (streamingState.value) {
    return 'border border-[#DDEBFA] bg-[#F3F8FF] shadow-sm'
  }
  return 'border border-neutral-200/90 bg-white/95 shadow-sm'
})

const textClass = computed(() => {
  if (isUser.value) {
    return 'font-medium text-slate-800'
  }
  if (errorText.value) {
    return 'text-red-700'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-800'
  }
  return 'text-text'
})

const statusClass = computed(() => {
  if (errorText.value) {
    return 'text-red-500'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-600'
  }
  return 'text-primary'
})

const timeClass = computed(() => {
  if (isUser.value) {
    return 'text-slate-500'
  }
  if (errorText.value) {
    return 'text-red-400'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-500'
  }
  return 'text-neutral-500'
})

const formattedTime = computed(() => {
  if (isStreamingActive.value) return '正在生成...'
  return formatTime(props.message.created_at)
})
</script>
