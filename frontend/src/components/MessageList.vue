<!-- 2025-01-07 - 消息列表美化：优雅布局与渐变背景 -->
<template>
  <div ref="containerRef" class="flex-1 overflow-y-auto">
    <div v-if="messages.length === 0" class="h-full flex items-center justify-center p-6">
      <div class="text-center">
        <div class="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-indigo-100 to-purple-100 mb-4">
          <svg class="w-10 h-10 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <p class="text-warm-400 font-medium">开始对话</p>
        <p class="text-warm-300 text-sm mt-1">发送消息与 AI 助手交流</p>
      </div>
    </div>
    <div v-else class="p-6 space-y-6">
      <MessageItem
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref, watchEffect } from 'vue'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import MessageItem from './MessageItem.vue'

const messagesStore = useMessagesStore()
const sessionsStore = useSessionsStore()

const messages = computed(() => messagesStore.displayMessages)
const containerRef = ref<HTMLElement | null>(null)

watch(() => sessionsStore.currentSessionId, (newId) => {
  if (newId) {
    messagesStore.fetchMessages(newId)
  }
}, { immediate: true })

watchEffect(() => {
  if (messagesStore.isStreaming && containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
})

const scrollToBottom = () => {
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
}

defineExpose({
  scrollToBottom
})
</script>
