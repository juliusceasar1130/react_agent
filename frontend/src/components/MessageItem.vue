<template>
  <div
    class="flex"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[70%] rounded-lg px-4 py-2"
      :class="messageClass"
    >
      <!-- 流式消息带光标效果 - 2025-01-01 -->
      <p class="text-sm whitespace-pre-wrap break-words">
        <template v-if="isStreaming">
          {{ content }}
          <span class="inline-block w-2 h-4 bg-blue-400 ml-1 animate-pulse"></span>
        </template>
        <template v-else>
          {{ content }}
        </template>
      </p>
      <p class="text-xs mt-1 opacity-60">
        {{ formattedTime }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Message, StreamingMessage } from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'

interface Props {
  message: Message | StreamingMessage
}

const props = defineProps<Props>()

const { formatTime } = useDateFormat()

const isUser = computed(() => props.message.role === 'user')

// 检测是否为流式消息 - 2025-01-01
const isStreaming = computed(() =>
  'isStreaming' in props.message && props.message.isStreaming
)

// 获取消息内容（兼容流式消息）- 2025-01-01
const content = computed(() =>
  isStreaming.value ? (props.message as StreamingMessage).content : props.message.content
)

const messageClass = computed(() => {
  if (isUser.value) {
    return 'bg-blue-500 text-white'
  }
  // 流式消息特殊样式 - 2025-01-01
  if (isStreaming.value) {
    return 'bg-blue-50 text-gray-800 border border-blue-200'
  }
  return 'bg-white text-gray-800 border border-gray-200'
})

// 格式化时间（流式消息显示"正在输入..."）- 2025-01-01
const formattedTime = computed(() => {
  if (isStreaming.value) return '正在输入...'
  return formatTime(props.message.created_at)
})
</script>
