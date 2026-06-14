<!-- 2026-04-19 23:40 Asia/Shanghai - 消息列表更新：聚焦阅读宽度与轻量空状态 -->
<template>
  <div class="relative min-h-0 flex-1">
    <div ref="containerRef" class="h-full overflow-y-auto overscroll-contain" @scroll="updateScrollState">
      <div v-if="messages.length === 0" class="flex h-full flex-col items-center justify-center px-4 animate-fade-in">
        <div class="mb-12 text-center">
          <div class="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-gradient-to-br from-primary/10 via-white to-accent/10 shadow-glow">
            <svg class="h-10 w-10 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h3 class="text-2xl font-bold text-text tracking-tight">您可以这样问我...</h3>
          <p class="mt-2 text-sm text-neutral-500">点击下方常用场景，或在输入框直接开始任务</p>
        </div>
        
        <div class="flex w-full max-w-2xl flex-wrap justify-center gap-3">
          <template v-for="domain in skillsStore.domains" :key="domain.name">
            <button 
              v-for="scenario in domain.scenarios" 
              :key="scenario.name"
              @click="handlePrototypeSubmit(scenario.questions[0])"
              class="rounded-full border border-neutral-200 bg-white px-5 py-2.5 text-sm font-medium text-neutral-600 shadow-sm transition hover:border-primary/40 hover:bg-primary/5 hover:text-primary hover:shadow-glow active:scale-95"
            >
              {{ scenario.title }}
            </button>
          </template>
        </div>
      </div>
      <div v-else class="mx-auto flex w-full max-w-5xl flex-col gap-5 px-1 py-2 sm:px-0">
        <MessageItem
          v-for="message in messages"
          :key="message.id"
          :message="message"
          @select-scenario="handlePrototypeSubmit"
        />
      </div>
    </div>

    <button
      v-if="showScrollToBottom"
      type="button"
      class="absolute bottom-5 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full border border-primary/25 bg-white px-5 py-2.5 text-sm font-medium text-primary shadow-lg backdrop-blur transition hover:border-primary/40 hover:shadow-xl active:scale-95"
      aria-label="滚动到底部"
      title="滚动到底部"
      @click="handleScrollToBottom"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m0 0l6-6m-6 6l-6-6" />
      </svg>
      <span>滚动到底部</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch, watchEffect } from 'vue'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import { useSkillsStore } from '@/stores/skills'
import MessageItem from './MessageItem.vue'

const emit = defineEmits<{
  (e: 'select-scenario', prompt: string): void
}>()

const skillsStore = useSkillsStore()

const messagesStore = useMessagesStore()
const sessionsStore = useSessionsStore()

const messages = computed(() => messagesStore.displayMessages)
const containerRef = ref<HTMLElement | null>(null)
const isNearBottom = ref(true)
const bottomThreshold = 96

const handlePrototypeSubmit = (prompt: string) => {
  emit('select-scenario', prompt)
}

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
