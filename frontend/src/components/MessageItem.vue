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

        <!-- 数据源与查询时刻脚标独立卡片化展示 -->
        <div
          v-if="!isUser && (metaData.queryTime || metaData.dataSource)"
          class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-neutral-100/50 pt-2.5 text-[11px] text-neutral-400 font-medium"
        >
          <span v-if="metaData.dataSource" class="flex items-center gap-1">
            <svg class="h-3.5 w-3.5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
            数据源: <code class="rounded bg-neutral-100 px-1 py-0.5 text-neutral-500 font-mono">{{ metaData.dataSource }}</code>
          </span>
          <span v-if="metaData.queryTime" class="flex items-center gap-1">
            <svg class="h-3.5 w-3.5 text-neutral-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            查询时刻: <span>{{ metaData.queryTime }}</span>
          </span>
        </div>

        <!-- 一键生成图表的智能快捷 Banner -->
        <div
          v-if="chartSuggestion"
          class="mt-4 flex flex-col gap-3 rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/5 via-white to-accent/5 p-3.5 shadow-sm sm:flex-row sm:items-center sm:justify-between animate-fade-in"
        >
          <div class="flex items-center gap-2.5">
            <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-glow">
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <div class="text-left">
              <div class="text-xs font-semibold text-neutral-800">一键生成图表</div>
              <div class="text-[11px] text-neutral-500 mt-0.5">
                {{ chartSuggestion.desc ? `检测到当前结果适合绘制：${chartSuggestion.desc}，点击一键绘制` : '检测到当前结果适合用图表展示，点击一键绘制' }}
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <button
              v-if="chartSuggestion.type === 'line' || chartSuggestion.type === 'auto'"
              type="button"
              class="rounded-xl border border-primary/20 bg-white px-3 py-1.5 text-xs font-semibold text-primary shadow-sm transition hover:bg-primary hover:text-white active:scale-95 whitespace-nowrap"
              @click="handleQuickChart('line')"
            >
              📈 生成折线图
            </button>
            <button
              v-if="chartSuggestion.type === 'bar' || chartSuggestion.type === 'auto'"
              type="button"
              class="rounded-xl border border-primary/20 bg-white px-3 py-1.5 text-xs font-semibold text-primary shadow-sm transition hover:bg-primary hover:text-white active:scale-95 whitespace-nowrap"
              @click="handleQuickChart('bar')"
            >
              📊 生成柱状图
            </button>
          </div>
        </div>
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

      <!-- 问答澄清卡片区域 -->
      <div
        v-if="!isUser && hasQuestions"
        class="px-4 pb-3 animate-fade-in"
      >
        <AskUserQuestionCard
          :questions="questions"
          :is-submitted="isQuestionSubmitted"
          @submit="handleQuestionSubmit"
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
          <p v-if="getToolArgsText(tool)" class="mt-1 max-h-24 overflow-hidden whitespace-pre-wrap break-all text-neutral-500">
            {{ getToolArgsText(tool) }}
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
            工具结果: {{ getToolNameById(toolResult.id) }} ({{ toolResult.id }})
          </summary>
          <pre class="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-relaxed text-neutral-500">{{ formatToolResultContent(toolResult.content) }}</pre>
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

      <!-- 反馈操作按钮与时间状态展示行 -->
      <div
        v-if="!isUser && !isStreamingActive && props.message.id && !props.message.id.startsWith('temp-')"
        class="flex items-center justify-between px-5 pb-3.5 pt-0 text-neutral-400 border-t border-neutral-100/50 mt-1"
      >
        <div class="flex items-center gap-4 mt-2">
          <button
            type="button"
            class="transition-colors duration-150 hover:text-primary active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-primary !font-semibold': props.message.feedback === 'like' }"
            @click="handleFeedback('like')"
          >
            👍 <span class="hidden sm:inline">赞</span>
          </button>
          <button
            type="button"
            class="transition-colors duration-150 hover:text-rose-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-rose-500 !font-semibold': props.message.feedback === 'dislike' }"
            @click="handleFeedback('dislike')"
          >
            👎 <span class="hidden sm:inline">踩</span>
          </button>
          <button
            type="button"
            class="transition-colors duration-150 hover:text-amber-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium bg-transparent border-none cursor-pointer"
            :class="{ 'text-amber-500 !font-semibold': props.message.feedback === 'collected' || props.message.feedback === 'approved' }"
            @click="handleFeedback(props.message.feedback === 'collected' || props.message.feedback === 'approved' ? 'none' : 'collected')"
          >
            ⭐ <span class="hidden sm:inline">{{ props.message.feedback === 'collected' || props.message.feedback === 'approved' ? '已收藏' : '收藏' }}</span>
          </button>
        </div>
        <div class="flex items-center gap-1 mt-2" :class="timeClass">
          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-xs">{{ formattedTime }}</span>
        </div>
      </div>
      <div
        v-else
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
import { computed, ref, watch } from 'vue'
import ChartArtifactCard from '@/components/ChartArtifactCard.vue'
import AskUserQuestionCard from '@/components/AskUserQuestionCard.vue'
import { useChatStream } from '@/composables/useChatStream'
import { triggerExportDownload } from '@/api/exports'
import { CHAT_DEBUG_STREAM } from '@/config/chat'
import { useMessagesStore } from '@/stores/messages'
import type {
  ChartArtifactRef,
  ExportArtifact,
  Message,
  StreamToolCall,
  StreamingMessage
} from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'
import { renderMarkdown, extractMetaData } from '@/utils/markdown'

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

const emit = defineEmits<{
  (e: 'select-scenario', prompt: string): void
}>()

const content = computed(() =>
  streamingState.value ? streamingState.value.content : props.message.content
)

const chartSuggestion = computed<{ type: 'line' | 'bar' | 'auto'; desc: string | null } | null>(() => {
  if (isUser.value || isStreamingActive.value) return null
  const rawContent = content.value || ''
  const match = rawContent.match(/\[suggest_chart:(line|bar|auto)(?:\|([^\]]+))?\]/)
  return match ? { type: match[1] as 'line' | 'bar' | 'auto', desc: match[2] || null } : null
})

const metaData = computed(() => {
  const { meta } = extractMetaData(content.value || '')
  return meta
})

const displayContent = computed(() => {
  const rawContent = content.value || ''
  const cleaned = rawContent.replace(/\[suggest_chart:(line|bar|auto)(?:\|[^\]]*)?\]/, '')
  const { cleanContent } = extractMetaData(cleaned)
  return cleanContent
})

const renderedContent = computed(() => renderMarkdown(displayContent.value))

const handleQuickChart = (type: 'line' | 'bar' | 'auto') => {
  const promptMap = {
    line: '生成折线图',
    bar: '生成柱状图',
    auto: '生成图表',
  }
  emit('select-scenario', promptMap[type])
}

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

// 澄清卡片相关逻辑
const questions = computed(() => {
  if (streamingState.value) {
    return streamingState.value.questions || []
  }
  return (props.message as Message).questions || []
})
const hasQuestions = computed(() => questions.value.length > 0)
const isLocalSubmitted = ref(false)

// 监听澄清问题包的深度变化，一旦有新问题推入（例如下一轮的澄清卡片）自动重置本地提交锁定状态
watch(
  () => questions.value,
  (newQuestions) => {
    if (newQuestions && newQuestions.length > 0) {
      isLocalSubmitted.value = false
    }
  },
  { deep: true }
)
const isQuestionSubmitted = computed(() => {
  if (!streamingState.value) {
    return true
  }
  return isLocalSubmitted.value
})
const { resumeMessage } = useChatStream()
const handleQuestionSubmit = async (answers: Record<string, string | string[]>) => {
  isLocalSubmitted.value = true
  try {
    await resumeMessage(answers)
  } catch (err) {
    isLocalSubmitted.value = false
    console.error('回复澄清失败:', err)
  }
}

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

const getToolArgsText = (tool: StreamToolCall): string => {
  if (tool.args_text) {
    return tool.args_text
  }
  if (tool.args) {
    if (typeof tool.args === 'object' && tool.args !== null) {
      const argsObj = tool.args as Record<string, unknown>
      if (typeof argsObj.query === 'string') {
        return argsObj.query
      }
      return JSON.stringify(tool.args, null, 2)
    }
    return String(tool.args)
  }
  return ''
}

const getToolNameById = (id: string): string => {
  const tool = toolCallList.value.find(t => t.id === id)
  return tool ? tool.name : id
}

const formatToolResultContent = (content: string): string => {
  try {
    const parsed = JSON.parse(content)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return content
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

const messagesStore = useMessagesStore()

const handleFeedback = async (feedbackType: 'none' | 'like' | 'dislike' | 'collected' | 'approved') => {
  if (!props.message.id) return
  try {
    await messagesStore.submitMessageFeedback(props.message.id, feedbackType)
  } catch (err) {
    console.error('Submit feedback failed:', err)
  }
}
</script>

<style scoped>
/* 2026-07-11 - Markdown 动态渲染元素与代码框美化 */
.message-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13.5px;
  line-height: 1.5;
  text-align: left;
  border-radius: 12px;
  overflow: hidden;
}

.message-markdown :deep(th) {
  background-color: #f8fafc;
  color: #334155;
  font-weight: 600;
  padding: 10px 14px;
  border-bottom: 2px solid #e2e8f0;
}

.message-markdown :deep(td) {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #475569;
}

.message-markdown :deep(tr:last-child td) {
  border-bottom: none;
}

.message-markdown :deep(tr:nth-child(even)) {
  background-color: rgba(248, 250, 252, 0.6);
}

.message-markdown :deep(tr:hover td) {
  background-color: rgba(241, 245, 249, 0.7);
  color: #0f172a;
}

/* SQL 代码块样式 */
.message-markdown :deep(pre) {
  position: relative;
  background-color: #0f172a;
  color: #f8fafc;
  padding: 16px;
  border-radius: 16px;
  margin: 12px 0;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.message-markdown :deep(pre::before) {
  content: 'SQL';
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.5px;
  background-color: #1e293b;
  padding: 2px 6px;
  border-radius: 6px;
}

.message-markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
</style>
