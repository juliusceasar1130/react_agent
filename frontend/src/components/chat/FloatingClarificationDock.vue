<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    enter-from-class="opacity-0 translate-y-3 scale-98"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition-all duration-200 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 translate-y-2 scale-98"
  >
    <div
      v-if="isAwaitingClarification"
      class="pointer-events-auto mb-2.5 flex items-center justify-between gap-3 rounded-xl border border-blue-200/90 bg-white/95 px-3.5 py-2.5 shadow-lg backdrop-blur-xl transition-all"
    >
      <div class="flex items-center gap-2.5 min-w-0">
        <span class="relative flex h-2.5 w-2.5 shrink-0">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-75"></span>
          <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-600"></span>
        </span>
        <div class="flex items-center gap-1.5 truncate text-xs font-semibold text-neutral-800">
          <span class="text-primary font-bold">【{{ displayAskerTitle }}】</span>
          <span class="text-neutral-600 font-medium">正在等待您确认参数...</span>
        </div>
      </div>

      <button
        type="button"
        @click="handleScrollToForm"
        class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-95 shrink-0 cursor-pointer"
      >
        <span>前往填写</span>
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useMessagesStore } from '@/stores/messages'
import { formatSubagentTitle } from '@/utils/helpers'

const sessionsStore = useSessionsStore()
const messagesStore = useMessagesStore()

const currentSessionId = computed(() => sessionsStore.currentSessionId)
const activeStreaming = computed(() => {
  if (!currentSessionId.value) return null
  return messagesStore.streamingMessagesMap[currentSessionId.value] || null
})

const isAwaitingClarification = computed(() => {
  if (!activeStreaming.value) return false
  return (
    activeStreaming.value.isInterrupted === true &&
    Array.isArray(activeStreaming.value.questions) &&
    activeStreaming.value.questions.length > 0
  )
})

const displayAskerTitle = computed(() => {
  if (!activeStreaming.value) return '智能助手'
  if (activeStreaming.value.interrupt_subagent_title) {
    return activeStreaming.value.interrupt_subagent_title
  }
  if (
    activeStreaming.value.interrupt_subagent_name &&
    activeStreaming.value.interrupt_subagent_name !== 'main'
  ) {
    return formatSubagentTitle(activeStreaming.value.interrupt_subagent_name)
  }
  return '智能助手'
})

const handleScrollToForm = () => {
  // 查找表单内部的输入框或卡片容器
  const inputEl = document.querySelector(
    '.ask-user-question-card textarea, .ask-user-question-card input, textarea[placeholder*="请在此输入"]'
  )
  if (inputEl) {
    inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (inputEl instanceof HTMLTextAreaElement || inputEl instanceof HTMLInputElement) {
      inputEl.focus()
    }
    return
  }

  const cardEl = document.querySelector('.ask-user-question-card') || document.querySelector('.animate-fade-in')
  if (cardEl) {
    cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}
</script>
