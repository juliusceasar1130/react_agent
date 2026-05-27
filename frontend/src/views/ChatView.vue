<!-- 2026-05-19 Asia/Shanghai - 智能分析助手主页面：方案 B 数据字典 Bento 看板与抽屉联动工作台 -->
<template>
  <div class="relative h-full w-full overflow-hidden bg-background text-text">
    <VariantB
      :isSidebarOpen="isSidebarOpen"
      :showBento="showBento"
      @closeSidebar="closeSidebar"
      @toggle-bento="toggleBento"
      @dblclick-cell="handleDblClickCell"
    >
      <template #sidebar-header-action>
        <button
          @click="handleCreateSession"
          class="btn-primary !rounded-2xl !px-4 !py-2 text-sm"
        >
          新建
        </button>
      </template>
      <template #sidebar-chat-list>
        <SessionList @selected="closeSidebar" />
      </template>
      <template #main-chat-area>
        <div class="flex h-full w-full flex-col overflow-hidden">
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

              <div class="flex items-center gap-2">
                <div class="flex items-center gap-2 rounded-full border border-neutral-200/80 bg-white/80 px-3 py-2 text-xs text-neutral-600 shadow-sm">
                  <span class="h-2 w-2 rounded-full" :class="isSending ? 'bg-primary animate-pulse' : 'bg-emerald-400'"></span>
                  {{ isSending ? '处理中' : '就绪' }}
                </div>
                <button
                  @click="toggleBento()"
                  class="flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-3 py-2 text-xs font-bold text-primary transition-all duration-200 hover:bg-primary hover:text-white shadow-glow whitespace-nowrap"
                >
                  <span>📚</span>
                  <span>{{ showBento ? '返回对话' : '数据字典看板' }}</span>
                </button>
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

            <MessageList v-if="currentSession" ref="messageListRef" @select-scenario="handleSelectScenario" />
            <WelcomeDashboard v-else @submit="handleDashboardSubmit" />
          </div>

          <div
            v-if="currentSession"
            class="relative z-10 border-t border-neutral-200/70 bg-white/70 px-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.5rem)] pt-2 backdrop-blur-xl sm:px-5 lg:px-8 lg:pt-3"
          >
            <div class="mx-auto w-full max-w-5xl panel p-2.5 sm:p-3">
              <div class="mb-2 flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex flex-col gap-1.5 sm:flex-row sm:items-center">
                  <ToggleSwitch
                    v-model="streamMode"
                    label="流式输出"
                    :show-status="true"
                    on-label="实时显示"
                    off-label="等待完整回复"
                  />
                  <ToggleSwitch
                    v-if="false"
                    v-model="enableThinking"
                    label="思考模式"
                    :show-status="true"
                    on-label="开启深度推理"
                    off-label="直达最终回答"
                    class="mt-1.5 sm:mt-0 sm:ml-4"
                  />
                </div>
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
                    ref="textareaRef"
                    v-model="inputText"
                    @keydown.enter.exact.prevent="handleSendMessage"
                    @keydown.enter.shift="inputText += '\n'"
                    placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
                    class="input min-h-[44px] resize-none pr-14 transition-all duration-200"
                    :class="{ 'input-glow': isInputHighlighted }"
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
        </div>
      </template>
    </VariantB>

    <!-- 极富设计感的毛玻璃 Toast 提示 -->
    <Transition name="toast-fade">
      <div
        v-if="toastVisible"
        class="fixed bottom-24 left-1/2 z-[60] -translate-x-1/2 rounded-full border border-primary/20 bg-white/80 px-4 py-2.5 text-xs font-semibold text-primary shadow-lg backdrop-blur-md flex items-center gap-2"
      >
        <span class="text-sm">✨</span>
        <span>{{ toastMessage }}</span>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import VariantB from '@/components/VariantB.vue'
import { useSessionsStore } from '@/stores/sessions'
import { useMessagesStore } from '@/stores/messages'
import { useChatStream } from '@/composables/useChatStream'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import SessionList from '@/components/SessionList.vue'
import MessageList from '@/components/MessageList.vue'
import WelcomeDashboard from '@/components/WelcomeDashboard.vue'

const sessionsStore = useSessionsStore()
const messagesStore = useMessagesStore()
const { isSending, streamMode, enableThinking, contextWarning, sendMessage, stopStreaming } = useChatStream()

const inputText = ref('')
const isSidebarOpen = ref(false)
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)

// 数据字典 Bento 控制（通过 props 下传 / emit 上传）
const showBento = ref(false)
function toggleBento() {
  showBento.value = !showBento.value
}

// 联动注入状态
const isInputHighlighted = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 极佳视觉提示 Toast 状态
const toastVisible = ref(false)
const toastMessage = ref('')
let toastTimer: any = null

/**
  * 双击数据字典单元格或字段名时，自动注入当前聊天输入框的光标位置并触发呼吸动效与 Toast 提示
  */
function handleDblClickCell(value: string) {
  const el = textareaRef.value
  if (!el) return

  const start = el.selectionStart
  const end = el.selectionEnd
  const text = inputText.value

  // 在光标位置无缝插入双击的文字，并保留前后内容
  inputText.value = text.substring(0, start) + value + text.substring(end)

  nextTick(() => {
    el.focus()
    const newPos = start + value.length
    el.setSelectionRange(newPos, newPos)

    // 1. 触发输入框闪烁聚焦微光反馈动效，提示用户已成功注入
    isInputHighlighted.value = true
    setTimeout(() => {
      isInputHighlighted.value = false
    }, 1000)

    // 2. 触发高保真 Toast 浮动气泡气泡提示
    toastMessage.value = `已成功提取 "${value}" 并自动注入输入框！`
    toastVisible.value = true
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toastVisible.value = false
    }, 1800)
  })
}

/**
 * 处理首页直接提问
 */
const handleDashboardSubmit = async (prompt: string) => {
  if (isSending.value) return
  
  // 1. 自动创建新会话（使用提问作为标题）
  const title = prompt.length > 20 ? prompt.substring(0, 20) + '...' : prompt
  await sessionsStore.createSession({ title })
  
  // 2. 填充输入框并发送
  inputText.value = prompt
  await handleSendMessage()
}

/**
 * 处理引导气泡场景选择
 */
const handleSelectScenario = async (prompt: string) => {
  if (isSending.value) return
  inputText.value = prompt
  await handleSendMessage()
}

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

// 侧边栏和输入状态
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

<style scoped>
/* 双击注入时，输入框边缘泛起极具呼吸感的微光聚焦动画 */
.input-glow {
  animation: glow-pulse 1s ease-in-out;
}

@keyframes glow-pulse {
  0%, 100% {
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.4);
    border-color: #2563eb;
  }
}

/* Toast Transition */
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-fade-enter-from {
  opacity: 0;
  transform: translate(-50%, 10px);
}
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
</style>

