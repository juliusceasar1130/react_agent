<template>
  <div ref="containerRef" class="flex-1 overflow-y-auto p-4">
    <div v-if="messages.length === 0" class="h-full flex items-center justify-center">
      <p class="text-gray-400">暂无消息</p>
    </div>
    <div v-else class="space-y-4">
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

// 使用 displayMessages 获取包含流式消息的列表 - 2025-01-01
const messages = computed(() => messagesStore.displayMessages)
const containerRef = ref<HTMLElement | null>(null)

// 监听会话变化
watch(() => sessionsStore.currentSessionId, (newId) => {
  if (newId) {
    messagesStore.fetchMessages(newId)
  }
}, { immediate: true })

// 流式消息时自动滚动 - 2025-01-01
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

// 暴露方法给父组件
defineExpose({
  scrollToBottom
})
</script>
