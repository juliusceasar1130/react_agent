<!-- 2026-04-19 23:40 Asia/Shanghai - 消息列表更新：聚焦阅读宽度与轻量空状态 -->
<template>
  <div class="relative min-h-0 flex-1">
    <div ref="containerRef" class="h-full overflow-y-auto overscroll-contain" @scroll="updateScrollState">
      <div v-if="messages.length === 0" class="flex h-full items-center justify-center px-2 py-6">
        <div class="panel w-full max-w-lg px-6 py-10 text-center">
          <div class="mb-4 inline-flex h-20 w-20 items-center justify-center rounded-[28px] bg-gradient-to-br from-primary/10 via-white to-accent/10">
            <svg class="h-10 w-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <p class="text-base font-semibold text-text">开始对话</p>
          <p class="mt-1 text-sm text-neutral-500">发送一条消息，和 AI 助手一起推进当前任务。</p>
        </div>
      </div>
      <div v-else class="mx-auto flex w-full max-w-5xl flex-col gap-5 px-1 py-2 sm:px-0">
        <MessageItem
          v-for="message in messages"
          :key="message.id"
          :message="message"
        />
      </div>
    </div>

    <button
      v-if="showScrollToBottom"
      type="button"
      class="absolute bottom-4 right-4 z-20 flex h-11 w-11 items-center justify-center rounded-full border border-primary/20 bg-white/95 text-primary shadow-soft backdrop-blur transition hover:border-primary/35 hover:bg-white active:scale-95 sm:right-6"
      aria-label="滚动到底部"
      title="滚动到底部"
      @click="handleScrollToBottom"
    >
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m0 0l6-6m-6 6l-6-6" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch, watchEffect } from 'vue'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import MessageItem from './MessageItem.vue'

const messagesStore = useMessagesStore()
const sessionsStore = useSessionsStore()

const messages = computed(() => messagesStore.displayMessages)
const containerRef = ref<HTMLElement | null>(null)
const isNearBottom = ref(true)
const bottomThreshold = 96

const showScrollToBottom = computed(() =>
  messagesStore.isStreaming && messages.value.length > 0 && !isNearBottom.value
)

const updateScrollState = () => {
  if (!containerRef.value) return

  const distanceToBottom = containerRef.value.scrollHeight
    - containerRef.value.scrollTop
    - containerRef.value.clientHeight
  isNearBottom.value = distanceToBottom <= bottomThreshold
}

function scrollToBottom(behavior: ScrollBehavior = 'auto') {
  if (containerRef.value) {
    containerRef.value.scrollTo({
      top: containerRef.value.scrollHeight,
      behavior,
    })
  }
}

watch(() => sessionsStore.currentSessionId, (newId) => {
  if (newId) {
    messagesStore.fetchMessages(newId)
  }
}, { immediate: true })

watchEffect(() => {
  if (messagesStore.isStreaming && isNearBottom.value && containerRef.value) {
    scrollToBottom()
  }
})

watch(messages, async () => {
  const shouldKeepBottom = isNearBottom.value
  await nextTick()
  if (shouldKeepBottom) {
    scrollToBottom()
  }
  updateScrollState()
}, { deep: true })

onMounted(() => {
  updateScrollState()
})

const handleScrollToBottom = () => {
  scrollToBottom('smooth')
  isNearBottom.value = true
}

defineExpose({
  scrollToBottom
})
</script>
