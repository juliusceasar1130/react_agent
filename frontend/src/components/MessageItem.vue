<!-- 2025-01-07 - 消息气泡美化：渐变设计与现代动画 -->
<template>
  <div
    class="flex animate-slide-up"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[75%] rounded-2xl shadow-sm transition-all duration-200"
      :class="messageWrapperClass"
    >
      <div class="px-5 py-3.5">
        <p class="text-[15px] leading-relaxed whitespace-pre-wrap break-words" :class="textClass">
          <template v-if="isStreaming">
            {{ content }}
            <span class="cursor-blink"></span>
          </template>
          <template v-else>
            {{ content }}
          </template>
        </p>
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
import type { Message, StreamingMessage } from '@/types'
import { useDateFormat } from '@/composables/useDateFormat'

interface Props {
  message: Message | StreamingMessage
}

const props = defineProps<Props>()

const { formatTime } = useDateFormat()

const isUser = computed(() => props.message.role === 'user')

const isStreaming = computed(() =>
  'isStreaming' in props.message && props.message.isStreaming
)

const content = computed(() =>
  isStreaming.value ? (props.message as StreamingMessage).content : props.message.content
)

const messageWrapperClass = computed(() => {
  if (isUser.value) {
    return 'bg-gradient-to-br from-indigo-500 to-purple-500'
  }
  if (isStreaming.value) {
    return 'bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200'
  }
  return 'bg-white border border-warm-200'
})

const textClass = computed(() => {
  if (isUser.value) {
    return 'text-white font-medium'
  }
  if (isStreaming.value) {
    return 'text-indigo-800'
  }
  return 'text-warm-800'
})

const timeClass = computed(() => {
  if (isUser.value) {
    return 'text-white/60'
  }
  return 'text-warm-400'
})

const formattedTime = computed(() => {
  if (isStreaming.value) return '正在输入...'
  return formatTime(props.message.created_at)
})
</script>
