<template>
  <div class="flex w-full h-full">
    <!-- 左侧：会话列表 -->
    <aside class="w-80 bg-white border-r border-gray-200 flex flex-col">
      <header class="p-4 border-b border-gray-200 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-gray-800">会话列表</h2>
        <button
          @click="handleCreateSession"
          class="px-3 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
        >
          新建
        </button>
      </header>
      <SessionList />
    </aside>

    <!-- 右侧：消息展示区 -->
    <main class="flex-1 flex flex-col bg-gray-50">
      <header v-if="currentSession" class="p-4 bg-white border-b border-gray-200">
        <h3 class="text-xl font-medium text-gray-800">{{ currentSession.title }}</h3>
      </header>
      <div v-else class="p-4 bg-white border-b border-gray-200">
        <p class="text-gray-400">选择或创建一个会话</p>
      </div>

      <!-- 消息列表 -->
      <MessageList v-if="currentSession" ref="messageListRef" />
      <EmptyState v-else />

      <!-- 消息输入区 -->
      <div v-if="currentSession" class="p-4 bg-white border-t border-gray-200">
        <!-- 流式模式开关 - 2025-01-01 -->
        <div class="flex items-center gap-2 mb-2">
          <label class="flex items-center gap-2 text-sm text-gray-600">
            <input
              v-model="streamMode"
              type="checkbox"
              class="w-4 h-4 text-blue-500 rounded focus:ring-blue-500"
            />
            流式输出
          </label>
          <span v-if="isSending" class="text-xs text-blue-500">
            {{ streamMode ? '正在接收流式响应...' : '正在发送...' }}
          </span>
        </div>

        <div class="flex gap-2">
          <textarea
            v-model="inputText"
            @keydown.enter.exact.prevent="handleSendMessage"
            @keydown.enter.shift="inputText += '\n'"
            placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
            class="flex-1 p-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows="2"
            :disabled="isSending"
          />
          <button
            @click="handleSendMessage"
            :disabled="!inputText.trim() || isSending"
            class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition self-end"
          >
            {{ isSending ? '发送中...' : '发送' }}
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStream } from '@/composables/useChatStream'  // 新增 - 2025-01-01
import SessionList from '@/components/SessionList.vue'
import MessageList from '@/components/MessageList.vue'
import EmptyState from '@/components/EmptyState.vue'

const sessionsStore = useSessionsStore()
// 使用流式聊天 composable - 2025-01-01
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
    // 使用新的 sendMessage 函数 - 2025-01-01
    await sendMessage(text)
    inputText.value = ''
    // 滚动到底部
    await nextTick()
    messageListRef.value?.scrollToBottom()
  } catch (err) {
    console.error('发送消息失败:', err)
    alert('发送消息失败，请重试')
  }
}
</script>
