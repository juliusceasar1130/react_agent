<!-- 2026-03-27 22:12 Asia/Shanghai - 默认仅展示最终结论，过程细节仅在调试模式显示 -->
<template>
  <div
    class="flex animate-slide-up"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[75%] rounded-2xl shadow-sm transition-all duration-200"
      :class="messageWrapperClass"
    >
      <div
        v-if="isInterruptedMessage && !isUser"
        class="px-5 pt-3 text-xs font-medium tracking-wide text-amber-600"
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
        <p class="text-[15px] leading-relaxed whitespace-pre-wrap break-words" :class="textClass">
          <template v-if="isStreamingActive">
            {{ content }}
            <span class="cursor-blink"></span>
          </template>
          <template v-else>
            {{ content }}
          </template>
        </p>
      </div>

      <div
        v-if="showDebugDetails && !isUser && toolCallList.length > 0"
        class="px-4 pb-3 space-y-2"
      >
        <div
          v-for="tool in toolCallList"
          :key="tool.id"
          class="rounded-xl border border-primary/15 bg-white/60 px-3 py-2 text-xs text-neutral-600"
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
        class="px-4 pb-3 space-y-2"
      >
        <details
          v-for="toolResult in toolResultEntries"
          :key="toolResult.id"
          class="rounded-xl border border-neutral-200 bg-surface/80 px-3 py-2 text-xs text-neutral-600"
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
        class="px-4 pb-2.5 pt-0 flex items-center justify-end gap-1.5"
        :class="timeClass"
      >
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="text-xs">{{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CHAT_DEBUG_STREAM } from '@/config/chat'
import type { Message, StreamToolCall, StreamingMessage } from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'

interface Props {
  message: Message | StreamingMessage
}

interface ToolResultEntry {
  id: string
  content: string
}

const props = defineProps<Props>()

const { formatTime } = useDateFormat()

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
  const message = props.message as Message
  const rawResults = streamingState.value?.toolResults ?? parseJson<Record<string, string>>(message.tool_results) ?? {}
  return Object.entries(rawResults).map(([id, result]) => ({
    id,
    content: String(result)
  }))
})

const hasToolResult = (toolId: string) => toolResultEntries.value.some(item => item.id === toolId)

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
    return 'bg-gradient-to-br from-primary to-primary-hover'
  }
  if (errorText.value) {
    return 'bg-gradient-to-br from-red-50 to-white border border-red-200'
  }
  if (isInterruptedMessage.value) {
    return 'bg-gradient-to-br from-amber-50 to-white border border-amber-200'
  }
  if (streamingState.value) {
    return 'bg-gradient-to-br from-primary/5 to-secondary/5 border border-primary/20'
  }
  return 'bg-surface border border-neutral-200'
})

const textClass = computed(() => {
  if (isUser.value) {
    return 'text-white font-medium'
  }
  if (errorText.value) {
    return 'text-red-700'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-800'
  }
  if (streamingState.value) {
    return 'text-primary'
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
    return 'text-white/60'
  }
  if (errorText.value) {
    return 'text-red-400'
  }
  if (isInterruptedMessage.value) {
    return 'text-amber-500'
  }
  return 'text-neutral-400'
})

const formattedTime = computed(() => {
  if (isStreamingActive.value) return '正在生成...'
  return formatTime(props.message.created_at)
})
</script>
