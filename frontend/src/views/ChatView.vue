<!-- 2026-04-19 23:40 Asia/Shanghai - 聊天界面方案 A：明亮卡片式布局与移动端抽屉 -->
<template>
  <div class="relative flex h-full w-full overflow-hidden">
    <div
      v-if="isSidebarOpen"
      class="fixed inset-0 z-30 bg-neutral-900/35 backdrop-blur-[2px] lg:hidden"
      @click="closeSidebar"
    ></div>

    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-[18.5rem] max-w-[86vw] flex-col border-r border-neutral-200/80 bg-white/95 shadow-2xl backdrop-blur-xl transition-transform duration-200 lg:static lg:z-auto lg:max-w-none lg:translate-x-0 lg:bg-white/80 lg:shadow-none"
      :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
    >
      <header class="flex items-center justify-between border-b border-neutral-200/80 px-4 py-4 sm:px-5">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-primary to-accent shadow-glow">
            <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <div>
            <p class="text-xs font-medium uppercase tracking-[0.22em] text-neutral-500">Workspace</p>
            <h2 class="text-lg font-semibold text-text">对话</h2>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="handleCreateSession"
            class="btn-primary !rounded-2xl !px-4 !py-2 text-sm"
          >
            新建
          </button>
          <button
            class="flex h-10 w-10 items-center justify-center rounded-2xl border border-neutral-200 bg-white text-neutral-500 transition hover:border-neutral-300 hover:text-text lg:hidden"
            @click="closeSidebar"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </header>

      <div class="border-b border-neutral-200/70 px-4 py-3 text-xs text-neutral-600 sm:px-5">
        在这里管理会话，保持不同话题的上下文更清晰。
      </div>

      <SessionList @selected="closeSidebar" />
    </aside>

    <main class="relative flex min-w-0 flex-1 flex-col overflow-hidden">
      <div class="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-white/60 to-transparent"></div>

      <header class="relative z-10 border-b border-neutral-200/70 bg-white/70 backdrop-blur-xl">
        <div class="mx-auto flex w-full max-w-6xl items-center gap-3 px-3 py-3 sm:px-5 lg:px-8">
          <button
            class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-neutral-200/90 bg-white text-neutral-600 shadow-sm transition hover:border-neutral-300 hover:text-text lg:hidden"
            @click="openSidebar"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div class="min-w-0 flex-1">
            <template v-if="currentSession">
              <div class="flex items-center gap-2">
                <span class="inline-flex h-2.5 w-2.5 rounded-full bg-accent"></span>
                <h3 class="truncate text-base font-semibold text-text sm:text-lg">{{ currentSession.title }}</h3>
              </div>
              <p class="mt-0.5 truncate text-sm" :class="streamHeaderClass">
                {{ streamHeaderText }}
              </p>
            </template>
            <template v-else>
              <p class="text-sm font-medium uppercase tracking-[0.18em] text-neutral-500">AI Chat Workspace</p>
              <p class="mt-1 text-sm text-neutral-600">选择或创建一个会话开始对话</p>
            </template>
          </div>

          <div class="hidden items-center gap-2 rounded-full border border-neutral-200/80 bg-white/80 px-3 py-2 text-xs text-neutral-600 shadow-sm sm:flex">
            <span class="h-2 w-2 rounded-full" :class="isSending ? 'bg-primary animate-pulse' : 'bg-emerald-400'"></span>
            {{ isSending ? '处理中' : '就绪' }}
          </div>
        </div>
      </header>

      <div class="relative flex min-h-0 flex-1 flex-col px-3 pb-3 pt-3 sm:px-5 lg:px-8 lg:pb-6">
        <div
          v-if="currentSession && contextWarning"
          class="animate-fade-in mx-auto mb-3 w-full max-w-5xl rounded-[22px] border border-amber-200/80 bg-amber-50/95 px-4 py-3 text-sm text-amber-900 shadow-sm"
        >
          <p class="font-semibold">当前上下文已接近安全阈值，建议新建对话。</p>
          <p class="mt-1 text-amber-800/90">
            估算输入 {{ contextWarning.estimated_input_tokens }} tokens，预警线 {{ contextWarning.warn_tokens }}，模型窗口 {{ contextWarning.context_window }}。
          </p>
        </div>

        <MessageList v-if="currentSession" ref="messageListRef" />
        <EmptyState v-else />
      </div>

      <div
        v-if="currentSession"
        class="relative z-10 border-t border-neutral-200/70 bg-white/70 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.5rem)] pt-2 backdrop-blur-xl sm:px-5 lg:px-8 lg:pt-3"
      >
        <div class="mx-auto w-full max-w-5xl panel p-2.5 sm:p-3">
          <div class="mb-2 flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
            <ToggleSwitch
              v-model="streamMode"
              label="流式输出"
              :show-status="true"
              on-label="实时显示"
              off-label="等待完整回复"
            />
            <span
              v-if="isSending"
              class="inline-flex items-center gap-1.5 self-start rounded-full px-2.5 py-0.5 text-[11px] font-medium sm:self-auto"
              :class="streamMode ? 'bg-primary/10 text-primary' : 'bg-neutral-100 text-neutral-500'"
            >
              <svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ streamMode ? '流式响应中...' : '发送中...' }}
            </span>
          </div>

          <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div class="relative flex-1">
              <textarea
                v-model="inputText"
                @keydown.enter.exact.prevent="handleSendMessage"
                @keydown.enter.shift="inputText += '\n'"
                placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                class="input min-h-[44px] resize-none pr-14"
                rows="1"
                :disabled="isSending"
              />
              <div
                v-if="inputText.length > 0"
                class="absolute bottom-2.5 right-3.5 rounded-full bg-white/90 px-2 py-0.5 text-[10px] text-neutral-500 shadow-sm"
              >
                {{ inputText.length }} 字符
              </div>
            </div>

            <button
              @click="isSending && streamMode ? handleStopStreaming() : handleSendMessage()"
              :disabled="!isSending && !inputText.trim()"
              class="flex h-10 items-center justify-center gap-1.5 rounded-2xl px-4 text-sm font-medium transition-all duration-200 sm:min-w-[110px]"
              :class="isSending && streamMode
                ? 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200 active:scale-[0.98]'
                : 'btn-primary'"
            >
              <svg v-if="!isSending" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              <svg v-else-if="streamMode" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 7h10v10H7z" />
              </svg>
              {{ isSending ? (streamMode ? '停止生成' : '发送中') : '发送' }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useMessagesStore } from '@/stores/messages'
import { useChatStream } from '@/composables/useChatStream'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import SessionList from '@/components/SessionList.vue'
import MessageList from '@/components/MessageList.vue'
import EmptyState from '@/components/EmptyState.vue'

const sessionsStore = useSessionsStore()
const messagesStore = useMessagesStore()
const { isSending, streamMode, contextWarning, sendMessage, stopStreaming } = useChatStream()

const currentSession = computed(() => sessionsStore.currentSession)
const currentStreamingMessage = computed(() => messagesStore.streamingMessage)
const streamHeaderText = computed(() => {
  if (currentStreamingMessage.value?.error) {
    return currentStreamingMessage.value.error
  }
  if (streamMode.value && currentStreamingMessage.value?.statusText) {
    return currentStreamingMessage.value.statusText
  }
  return 'AI 智能助手'
})
const streamHeaderClass = computed(() => {
  if (currentStreamingMessage.value?.error) {
    return 'text-sm text-red-500'
  }
  if (streamMode.value && currentStreamingMessage.value?.statusText) {
    return 'text-sm text-primary'
  }
  return 'text-sm text-neutral-500'
})
const inputText = ref('')
const isSidebarOpen = ref(false)
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)

const openSidebar = () => {
  isSidebarOpen.value = true
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const handleCreateSession = async () => {
  await sessionsStore.createSession({ title: '新对话' })
  closeSidebar()
}

const handleSendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || !currentSession.value || isSending.value) return

  try {
    await sendMessage(text)
    inputText.value = ''
    await nextTick()
    messageListRef.value?.scrollToBottom()
  } catch (err) {
    console.error('发送消息失败:', err)
    alert('发送消息失败，请重试')
  }
}

const handleStopStreaming = () => {
  if (!isSending.value || !streamMode.value) return
  stopStreaming()
}
</script>
