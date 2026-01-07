<!-- 2025-01-07 - 主界面美化：现代布局与优雅配色 -->
<template>
  <div class="flex w-full h-full">
    <!-- 左侧：会话列表 -->
    <aside class="w-80 bg-white border-r border-warm-200 flex flex-col shadow-soft">
      <header class="p-5 border-b border-warm-200 flex justify-between items-center bg-gradient-to-r from-warm-50 to-white">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-glow">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 class="text-lg font-semibold text-warm-800">对话</h2>
        </div>
        <button
          @click="handleCreateSession"
          class="btn-primary !px-4 !py-2 !text-sm flex items-center gap-1.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          新建
        </button>
      </header>
      <SessionList />
    </aside>

    <!-- 右侧：消息展示区 -->
    <main class="flex-1 flex flex-col bg-gradient-to-br from-warm-50 via-white to-indigo-50/30">
      <header v-if="currentSession" class="px-6 py-4 bg-white/80 backdrop-blur-sm border-b border-warm-200 shadow-sm animate-fade-in">
        <h3 class="text-xl font-semibold text-warm-800">{{ currentSession.title }}</h3>
        <p class="text-sm text-warm-500 mt-0.5">AI 智能助手</p>
      </header>
      <div v-else class="px-6 py-4 bg-white/80 backdrop-blur-sm border-b border-warm-200">
        <p class="text-warm-400">选择或创建一个会话开始对话</p>
      </div>

      <!-- 消息列表 -->
      <MessageList v-if="currentSession" ref="messageListRef" />
      <EmptyState v-else />

      <!-- 消息输入区 -->
      <div v-if="currentSession" class="p-4 bg-white/80 backdrop-blur-sm border-t border-warm-200">
        <!-- 流式模式开关 - 2025-01-07 使用 ToggleSwitch 组件 -->
        <div class="flex items-center justify-between mb-3">
          <ToggleSwitch
            v-model="streamMode"
            label="流式输出"
            :show-status="true"
            on-label="实时显示"
            off-label="等待完整回复"
          />
          <span v-if="isSending" class="text-xs flex items-center gap-1.5 animate-pulse px-2.5 py-1 rounded-full"
            :class="streamMode ? 'bg-indigo-50 text-indigo-600' : 'bg-warm-100 text-warm-600'"
          >
            <svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ streamMode ? '流式响应中...' : '发送中...' }}
          </span>
        </div>

        <div class="flex gap-3">
          <div class="flex-1 relative">
            <textarea
              v-model="inputText"
              @keydown.enter.exact.prevent="handleSendMessage"
              @keydown.enter.shift="inputText += '\n'"
              placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
              class="input resize-none"
              rows="2"
              :disabled="isSending"
            />
              <div
                v-if="inputText.length > 0"
                class="absolute bottom-3 right-3 text-xs text-warm-400 transition-opacity duration-200"
              >
                {{ inputText.length }} 字符
              </div>
          </div>
          <button
            @click="handleSendMessage"
            :disabled="!inputText.trim() || isSending"
            class="btn-primary self-end flex items-center gap-2 !px-5"
          >
            <svg v-if="!isSending" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            {{ isSending ? '发送中' : '发送' }}
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStream } from '@/composables/useChatStream'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import SessionList from '@/components/SessionList.vue'
import MessageList from '@/components/MessageList.vue'
import EmptyState from '@/components/EmptyState.vue'

const sessionsStore = useSessionsStore()
const { isSending, streamMode, sendMessage } = useChatStream()

const currentSession = computed(() => sessionsStore.currentSession)
const inputText = ref('')
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)

const handleCreateSession = async () => {
  await sessionsStore.createSession({ title: '新对话' })
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
</script>
