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
          v-if="isSlim"
          @click="handleCreateSession"
          class="bg-primary hover:bg-primary-hover text-white !rounded-full w-10 h-10 flex items-center justify-center shadow-glow shrink-0 transition-all duration-200 hover:scale-105 active:scale-95"
          title="新建会话"
        >
          <svg class="h-5 w-5 text-white" fill="none" stroke="white" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <button
          v-else
          @click="handleCreateSession"
          class="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white shadow-2xs transition-all hover:bg-blue-700 active:scale-95 shrink-0 cursor-pointer"
        >
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          <span>新建</span>
        </button>
      </template>
      <template #sidebar-chat-list>
        <SessionList :isSlim="isSlim" @selected="closeSidebar" />
      </template>
      <template #main-chat-area>
        <div class="flex h-full w-full flex-col overflow-hidden">
          <header class="sticky top-0 z-20 w-full bg-background/80 backdrop-blur-md transition-colors">
            <div class="mx-auto flex w-full max-w-6xl items-center gap-3 px-4 sm:px-0 py-3">
              <button
                @click="isSidebarOpen = !isSidebarOpen"
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
                :title="isSidebarOpen ? '收起侧边栏' : '展开侧边栏'"
              >
                <svg v-if="isSidebarOpen" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="18" height="18" x="3" y="3" rx="2.5"/>
                  <path d="M9 3v18"/>
                  <path d="m14 9-3 3 3 3"/>
                </svg>
                <svg v-else class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect width="18" height="18" x="3" y="3" rx="2.5"/>
                  <path d="M9 3v18"/>
                  <path d="m13 15 3-3-3-3"/>
                </svg>
              </button>

              <div class="min-w-0 flex-1">
                <template v-if="currentSession">
                  <div class="flex items-center gap-2 truncate">
                    <div class="flex h-6 w-6 items-center justify-center rounded-md bg-neutral-100/90 text-neutral-600 border border-neutral-200/80 shadow-2xs shrink-0">
                      <svg class="h-3.5 w-3.5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                      </svg>
                    </div>
                    <h3 class="truncate text-sm sm:text-base font-semibold text-neutral-800 tracking-tight">{{ currentSession.title }}</h3>
                  </div>
                </template>
                <template v-else>
                  <p class="text-xs font-medium uppercase tracking-[0.15em] text-neutral-400">AI Chat Workspace</p>
                </template>
              </div>

              <div class="flex items-center gap-1.5">
                <div class="flex items-center gap-1.5 rounded-lg border border-neutral-200/80 bg-neutral-50/80 px-2.5 py-1 text-xs font-medium text-neutral-600">
                  <span class="h-2 w-2 rounded-full shrink-0" :class="isSending ? 'bg-primary animate-pulse' : 'bg-emerald-500'"></span>
                  <span>{{ isSending ? '处理中' : '就绪' }}</span>
                </div>
                <button
                  @click="showChangelog = true"
                  class="flex items-center gap-1.5 rounded-lg border border-neutral-200/80 bg-white/80 px-2.5 py-1 text-xs font-medium text-neutral-600 transition-all duration-150 hover:bg-white hover:border-neutral-300 hover:text-neutral-900 shadow-2xs whitespace-nowrap"
                  title="关于与更新日志"
                >
                  <svg class="h-3.5 w-3.5 text-neutral-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>关于</span>
                </button>
                <button
                  v-if="showAdminReviewBtn"
                  @click="toggleAdminReview()"
                  class="flex items-center gap-1.5 rounded-lg border border-neutral-200/80 bg-white/80 px-2.5 py-1 text-xs font-medium text-neutral-600 transition-all duration-150 hover:bg-white hover:border-neutral-300 hover:text-neutral-900 shadow-2xs whitespace-nowrap"
                  :class="showAdminReview ? 'border-amber-300 bg-amber-50/90 text-amber-800' : ''"
                >
                  <svg class="h-3.5 w-3.5 text-neutral-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span>{{ showAdminReview ? '返回对话' : '审核终端' }}</span>
                </button>
                <button
                  @click="toggleBento()"
                  class="flex items-center gap-1.5 rounded-lg border border-neutral-200/80 bg-white/80 px-2.5 py-1 text-xs font-medium text-neutral-600 transition-all duration-150 hover:bg-white hover:border-primary/40 hover:text-primary shadow-2xs whitespace-nowrap"
                  :class="showBento ? 'border-primary/40 bg-primary/5 text-primary' : ''"
                >
                  <svg class="h-3.5 w-3.5 text-neutral-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  <span>{{ showBento ? '返回对话' : '数据字典看板' }}</span>
                </button>
              </div>
            </div>
          </header>

          <div class="relative flex min-h-0 flex-1 flex-col w-full">
            <div
              v-if="currentSession && contextWarning"
              class="animate-fade-in mx-auto mb-3 flex w-full max-w-6xl items-center justify-between gap-3 rounded-xl border border-amber-200/80 bg-amber-50/95 px-4 py-3 text-sm text-amber-900 shadow-2xs backdrop-blur-md shrink-0"
            >
              <div class="flex items-center gap-3 min-w-0 flex-1">
                <svg class="h-5 w-5 text-amber-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div class="min-w-0 flex-1">
                  <p class="font-semibold text-amber-950 tracking-tight">当前上下文已接近安全阈值，建议新建对话。</p>
                  <p class="mt-0.5 text-xs text-amber-800/90 font-mono">
                    估算输入 <span class="font-bold text-amber-900">{{ contextWarning.estimated_input_tokens }}</span> tokens · 预警线 {{ contextWarning.warn_tokens }} · 模型窗口 {{ contextWarning.context_window }}
                  </p>
                </div>
              </div>

              <button
                @click="handleCreateSession"
                class="flex items-center gap-1.5 rounded-lg bg-amber-900 px-3 py-1.5 text-xs font-medium text-amber-50 hover:bg-amber-950 active:scale-95 transition-all shadow-2xs shrink-0 cursor-pointer"
              >
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                <span>新建对话</span>
              </button>
            </div>

            <MessageList v-if="currentSession" ref="messageListRef" @select-scenario="handleSelectScenario" />
            <WelcomeDashboard
              v-else
              @submit="handleDashboardSubmit"
              @quick-view="handleQuickView"
            />
          </div>

          <div
            v-if="currentSession"
            class="sticky bottom-3 sm:bottom-4 z-20 mx-auto w-full max-w-6xl px-3 sm:px-0 pointer-events-none mb-2 sm:mb-3"
          >
            <div class="pointer-events-auto rounded-xl border border-neutral-200/80 bg-white/95 shadow-md backdrop-blur-xl p-3.5 sm:p-4 transition-all duration-200">
              <div class="flex flex-col gap-2.5">
                <!-- 输入文本域 -->
                <div class="relative">
                  <textarea
                    ref="textareaRef"
                    v-model="inputText"
                    @keydown.enter.exact.prevent="handleSendMessage"
                    @keydown.enter.shift="inputText += '\n'"
                    placeholder="从任何想法开始... (Enter 发送，Shift+Enter 换行)"
                    class="w-full bg-transparent border-0 focus:ring-0 focus:outline-none min-h-[52px] max-h-[180px] resize-none text-sm text-neutral-800 placeholder:text-neutral-400 py-1.5 leading-relaxed"
                    :class="{ 'input-glow': isInputHighlighted }"
                    rows="1"
                    :disabled="isSending"
                  />
                </div>

                <!-- 底部工具栏 -->
                <div class="flex items-center justify-between pt-2.5 border-t border-neutral-100">
                  <div class="flex items-center gap-2">
                    <ToggleSwitch
                      v-model="streamMode"
                      label="流式输出"
                      :show-status="true"
                      on-label="实时显示"
                      off-label="等待完整"
                    />
                    <div class="h-3.5 w-px bg-neutral-200/80 mx-0.5"></div>
                    <ToggleSwitch
                      v-model="enableThinking"
                      label="深度思考"
                      :show-status="true"
                      on-label="已开启"
                      off-label="已关闭"
                    />
                    <span
                      v-if="isSending"
                      class="inline-flex items-center gap-1.5 rounded-md bg-neutral-100 px-2.5 py-1 text-[11px] font-medium text-neutral-600"
                    >
                      <svg class="h-3 w-3 animate-spin text-primary" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {{ streamMode ? '流式中...' : '发送中...' }}
                    </span>
                  </div>

                  <div class="flex items-center gap-3">
                    <span v-if="inputText.length > 0" class="text-xs font-mono text-neutral-400 hidden sm:inline">
                      {{ inputText.length }} 字符
                    </span>
                    <button
                      @click="isSending && streamMode ? handleStopStreaming() : handleSendMessage()"
                      :disabled="!isSending && !inputText.trim()"
                      class="flex h-9 w-9 items-center justify-center rounded-lg transition-all duration-150 shrink-0 cursor-pointer"
                      :class="isSending && streamMode
                        ? 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200/80 active:scale-95'
                        : (!inputText.trim() && !isSending ? 'bg-neutral-100 text-neutral-400 border border-neutral-200/60 cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700 active:scale-95 shadow-2xs')"
                      :title="isSending ? (streamMode ? '停止生成' : '发送中...') : '发送消息 (Enter)'"
                    >
                      <svg v-if="!isSending" class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                      <svg v-else-if="streamMode" class="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M7 7h10v10H7z" />
                      </svg>
                      <svg v-else class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

    </VariantB>

    <!-- 右侧直通场景毛玻璃悬浮卡片组 -->
    <FloatingScenarioCards />

    <!-- 场景直通弹窗组件 -->
    <ScenarioModal @cell-dblclick="handleDblClickCell" />

    <VersionChangelogModal v-model:show="showChangelog" />
    <AdminReviewPanel v-model:show="showAdminReview" />

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
import { computed, nextTick, ref, onMounted, onUnmounted } from 'vue'
import VariantB from '@/components/VariantB.vue'
import { useSessionsStore } from '@/stores/sessions'
import { useChatStream } from '@/composables/useChatStream'
import ToggleSwitch from '@/components/ToggleSwitch.vue'
import SessionList from '@/components/SessionList.vue'
import MessageList from '@/components/MessageList.vue'
import WelcomeDashboard from '@/components/WelcomeDashboard.vue'
import VersionChangelogModal from '@/components/VersionChangelogModal.vue'
import AdminReviewPanel from '@/components/AdminReviewPanel.vue'
import FloatingScenarioCards from '@/components/FloatingScenarioCards.vue'
import ScenarioModal from '@/components/ScenarioModal.vue'
import { useScenarioPanelStore } from '@/stores/scenarioPanel'

const sessionsStore = useSessionsStore()
const scenarioPanelStore = useScenarioPanelStore()
const { isSending, streamMode, enableThinking, contextWarning, sendMessage, stopStreaming } = useChatStream()

const inputText = ref('')
const isSidebarOpen = ref(false)
const messageListRef = ref<InstanceType<typeof MessageList> | null>(null)

// 锁死变体 C（微缩侧边栏）下折叠态表现
const isSlim = computed(() => {
  return !isSidebarOpen.value
})

// 数据字典 Bento 控制（通过 props 下传 / emit 上传）
const showBento = ref(false)
const showChangelog = ref(false)
const showAdminReview = ref(false)
const showAdminReviewBtn = ref(false)

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.ctrlKey && (e.key === 'm' || e.key === 'M')) {
    e.preventDefault()
    showAdminReviewBtn.value = !showAdminReviewBtn.value
  }
}

function toggleBento() {
  showBento.value = !showBento.value
  if (showAdminReview.value) showAdminReview.value = false
}
function toggleAdminReview() {
  showAdminReview.value = !showAdminReview.value
  if (showBento.value) showBento.value = false
}

// 联动注入状态
const isInputHighlighted = ref(false)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 极佳视觉提示 Toast 状态
const toastVisible = ref(false)
const toastMessage = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function handleQuickView(domain: string, scenario: string) {
  scenarioPanelStore.open(domain, scenario)
}

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

// 侧边栏和输入状态

const closeSidebar = () => {
  // 仅在移动端/小屏幕尺寸下，才在点击列表中会话项时自动收回侧边栏
  if (window.innerWidth < 1024) {
    isSidebarOpen.value = false
  }
}

const handleCreateSession = async () => {
  if (isSending.value) return
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


onMounted(() => {
  sessionsStore.fetchSessions()
  scenarioPanelStore.fetchDomainTree()
  // 智能适配大屏初始状态下侧边栏的开合状态（大屏默认展开）
  isSidebarOpen.value = window.innerWidth >= 1024
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
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

