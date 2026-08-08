<!-- 2026-06-29 Asia/Shanghai - 管理员黄金案例审核终端面板 (阶段四) -->
<template>
  <Transition name="modal-fade">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      <!-- 背景遮罩 overlay -->
      <div
        class="fixed inset-0 bg-neutral-900/40 backdrop-blur-md transition-opacity"
        @click="closeModal"
      ></div>

      <!-- 弹窗容器 container -->
      <div
        class="relative z-10 flex h-[85vh] w-[95vw] max-w-6xl flex-col overflow-hidden rounded-[28px] bg-white border border-neutral-200/50 shadow-2xl transition-all duration-300 backdrop-blur-2xl"
      >
        <!-- 右上角关闭按钮 -->
        <button
          @click="closeModal"
          class="absolute top-4 right-4 z-20 flex h-8 w-8 items-center justify-center rounded-full text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 transition-colors"
          title="关闭审核终端"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div class="flex h-full w-full flex-col overflow-hidden">
    <!-- 头部 -->
    <div class="flex shrink-0 items-start justify-between border-b border-neutral-200/80 bg-white/80 px-6 py-4 backdrop-blur-xl">
      <div>
        <div class="flex items-center gap-2">
          <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-base">⚙️</span>
          <h2 class="text-lg font-bold text-neutral-800">黄金案例审核终端</h2>
          <span
            v-if="pendingList.length > 0"
            class="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-bold text-white"
          >
            {{ pendingList.length }}
          </span>
        </div>
        <p class="mt-1 text-sm text-neutral-500">
          审查 LLM 预提纯草稿，修正后一键导入向量库，建立持续演进的 Few-shot 知识基础。
        </p>
      </div>
      <button
        @click="fetchPendingList"
        :disabled="loading"
        class="flex shrink-0 items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-3.5 py-2 text-xs font-medium text-neutral-600 shadow-sm transition hover:bg-neutral-50 active:scale-95 disabled:opacity-50 mr-10"
      >
        <svg class="h-3.5 w-3.5 transition-transform" :class="loading ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        {{ loading ? '刷新中...' : '刷新列表' }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading && pendingList.length === 0" class="flex flex-1 flex-col items-center justify-center gap-4">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
      <p class="text-sm text-neutral-500">正在拉取待审核案例...</p>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading && pendingList.length === 0"
      class="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center"
    >
      <div class="flex h-20 w-20 items-center justify-center rounded-[28px] bg-emerald-50 text-4xl shadow-sm">🎉</div>
      <div>
        <h3 class="text-base font-semibold text-neutral-700">暂无待审核案例</h3>
        <p class="mt-1.5 max-w-xs text-sm text-neutral-400">
          所有收藏案例均已处理完毕。当用户在聊天界面点击 ⭐ 收藏 SQL 回答后，案例会在此处出现。
        </p>
      </div>
    </div>

    <!-- 案例列表 -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-4 sm:px-6 lg:px-8">
      <div class="mx-auto max-w-5xl space-y-5">
        <div
          v-for="item in pendingList"
          :key="item.id"
          class="overflow-hidden rounded-[22px] border border-neutral-200/90 bg-white shadow-sm transition-shadow hover:shadow-md"
        >
          <!-- 卡片头部 -->
          <div class="flex items-center justify-between border-b border-neutral-100 px-5 py-3">
            <div class="flex items-center gap-2">
              <span class="inline-flex items-center gap-1 rounded-lg bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">
                ⭐ 待审核
              </span>
              <span class="rounded bg-neutral-100 px-1.5 py-0.5 text-xs font-mono text-neutral-500">
                {{ item.id.slice(0, 8) }}...
              </span>
              <span v-if="editForms[item.id]?.domain && editForms[item.id].domain !== 'general'"
                class="rounded bg-accent/15 px-1.5 py-0.5 text-xs font-semibold text-accent"
              >
                {{ editForms[item.id].domain }}
              </span>
            </div>
            <span class="text-xs text-neutral-400">{{ formatTime(item.created_at) }}</span>
          </div>

          <!-- 卡片主体：左右两列 -->
          <div class="grid grid-cols-1 gap-0 md:grid-cols-2">
            <!-- 左侧：原始上下文参考 -->
            <div class="border-b border-neutral-100 p-5 md:border-b-0 md:border-r">
              <div class="mb-3 flex items-center gap-1.5 text-xs font-semibold text-neutral-500 uppercase tracking-wide">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                </svg>
                原始用户提问
              </div>
              <div class="rounded-xl bg-neutral-50 p-3.5 text-sm text-neutral-700 leading-relaxed border border-neutral-100 min-h-[60px]">
                {{ item.content }}
              </div>

              <div class="mt-4 mb-3 flex items-center gap-1.5 text-xs font-semibold text-neutral-500 uppercase tracking-wide">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
                </svg>
                原始 SQL
              </div>
              <div class="rounded-xl bg-neutral-900 p-3.5 min-h-[80px] overflow-x-auto">
                <pre class="text-xs font-mono text-emerald-400 leading-relaxed whitespace-pre-wrap">{{ parseOriginalSql(item) || '（无 SQL 记录）' }}</pre>
              </div>
            </div>

            <!-- 右侧：LLM 草稿编辑区 -->
            <div class="p-5 flex flex-col gap-4">
              <div class="mb-1 flex items-center gap-1.5 text-xs font-semibold text-primary uppercase tracking-wide">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.344.344a3.999 3.999 0 01-.633.467A4 4 0 0112 17.5a4 4 0 01-2.636-1.003l-.343-.344z"/>
                </svg>
                ✨ LLM 提炼意图（可修改）
              </div>

              <div v-if="editForms[item.id]">
                <input
                  type="text"
                  v-model="editForms[item.id].custom_query"
                  placeholder="LLM 改写后的标准自然语言提问..."
                  class="w-full rounded-xl border border-neutral-200 px-3.5 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 shadow-sm"
                />

                <div class="mt-4 mb-3 flex items-center gap-1.5 text-xs font-semibold text-primary uppercase tracking-wide">
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
                  </svg>
                  🔑 脱敏参数化 SQL（可修改）
                </div>
                <textarea
                  v-model="editForms[item.id].custom_sql"
                  rows="5"
                  placeholder="LLM 参数化脱敏后的 SQL 模板，例如：SELECT * FROM t WHERE date = :date_param"
                  class="w-full rounded-xl border border-neutral-200 p-3.5 text-xs font-mono outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 shadow-sm leading-relaxed resize-none"
                ></textarea>

                <!-- 提示：草稿来源 -->
                <div v-if="!item.refined_payload" class="mt-2 flex items-start gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  <span class="mt-0.5 shrink-0">⚠️</span>
                  <span>该案例尚未完成后台 LLM 预提炼，内容为原始数据，请仔细手动核验后再入库。</span>
                </div>

                <!-- 操作按钮 -->
                <div class="mt-4 flex items-center justify-end gap-3 border-t border-neutral-100 pt-4">
                  <button
                    @click="handleReject(item.id)"
                    :disabled="!!submitting[item.id]"
                    class="flex items-center gap-1.5 rounded-full border border-neutral-200 bg-white px-4 py-2 text-xs font-medium text-neutral-600 shadow-sm transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                    忽略/拒绝
                  </button>
                  <button
                    @click="handleApprove(item.id)"
                    :disabled="!!submitting[item.id] || !editForms[item.id].custom_query || !editForms[item.id].custom_sql"
                    class="flex items-center gap-1.5 rounded-full bg-primary px-5 py-2 text-xs font-bold text-white shadow-glow transition hover:bg-primary-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <svg v-if="submitting[item.id]" class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
                    </svg>
                    {{ submitting[item.id] ? '正在入库...' : '确认并导入' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast 通知 -->
    <Transition name="toast">
      <div
        v-if="toast.visible"
        class="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium shadow-lg"
        :class="toast.type === 'success' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'"
      >
        <span>{{ toast.type === 'success' ? '✅' : '❌' }}</span>
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import api from '@/api'
import type { Message } from '@/types'
import { parseJson } from '@/utils/helpers'

// ---- Props & Emits ----
const props = withDefaults(
  defineProps<{
    show: boolean
  }>(),
  {
    show: false
  }
)

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
}>()

const closeModal = () => {
  emit('update:show', false)
}

// ---- State ----
const pendingList = ref<Message[]>([])
const loading = ref(false)
const submitting = ref<Record<string, boolean>>({})
const editForms = ref<Record<string, { custom_query: string; custom_sql: string; domain: string }>>({})

const toast = ref({ visible: false, type: 'success', message: '' })

// 监听弹窗显示状态控制 body 滚动与刷新
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      document.body.classList.add('overflow-hidden')
      fetchPendingList()
    } else {
      document.body.classList.remove('overflow-hidden')
    }
  }
)

// 处理 ESC 按键关闭
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.show) {
    closeModal()
  }
}

// ---- Helpers ----
function parseOriginalSql(item: Message): string {
  if (item.tool_calls) {
    const calls = parseJson<Array<{ name: string; args?: { query?: string } }>>(item.tool_calls)
    if (!calls) return ''
    const sqlCalls = calls.filter(tc => tc.name === 'sql_db_query' && tc.args?.query)

      if (sqlCalls.length === 1 && sqlCalls[0].args?.query) {
        return sqlCalls[0].args.query
      } else if (sqlCalls.length > 1) {
        return sqlCalls.map((tc: any, idx: number) => {
          return `-- Step ${idx + 1}\n${tc.args.query.trim()};`
        }).join('\n\n')
      }
  }
  return ''
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch (_) {
    return ts
  }
}

function showToast(type: 'success' | 'error', message: string) {
  toast.value = { visible: true, type, message }
  setTimeout(() => { toast.value.visible = false }, 3000)
}

function initForm(item: Message) {
  let rewrittenQuery = ''
  let desensitizedSql = ''
  let domain = 'general'

  if (item.refined_payload) {
    const data = parseJson<{ rewritten_query?: string; desensitized_sql?: string; domain?: string }>(item.refined_payload)
    if (data) {
      rewrittenQuery = data.rewritten_query || ''
      desensitizedSql = data.desensitized_sql || ''
      domain = data.domain || 'general'
    }
  }

  // 兜底：无草稿时用原始内容
  if (!rewrittenQuery) rewrittenQuery = item.content || ''
  if (!desensitizedSql) desensitizedSql = parseOriginalSql(item)

  editForms.value[item.id] = { custom_query: rewrittenQuery, custom_sql: desensitizedSql, domain }
}

// ---- API calls ----
async function fetchPendingList() {
  loading.value = true
  try {
    const data: Message[] = await api.get('/api/chat/admin/messages/pending')
    pendingList.value = data
    data.forEach(item => initForm(item))
  } catch (e) {
    showToast('error', '获取待审核案例失败，请检查后端连接')
  } finally {
    loading.value = false
  }
}

async function handleApprove(id: string) {
  submitting.value[id] = true
  const form = editForms.value[id]
  try {
    await api.post(`/api/chat/admin/messages/${id}/approve`, {
      custom_query: form.custom_query,
      custom_sql: form.custom_sql
    })
    pendingList.value = pendingList.value.filter(item => item.id !== id)
    delete editForms.value[id]
    showToast('success', '案例已成功导入向量库！')
  } catch (e) {
    showToast('error', '入库失败，请检查向量库连接状态')
  } finally {
    submitting.value[id] = false
  }
}

async function handleReject(id: string) {
  submitting.value[id] = true
  try {
    await api.post(`/api/chat/messages/${id}/feedback`, { feedback: 'none' })
    pendingList.value = pendingList.value.filter(item => item.id !== id)
    delete editForms.value[id]
    showToast('success', '已忽略该案例')
  } catch (e) {
    showToast('error', '操作失败，请重试')
  } finally {
    submitting.value[id] = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  if (props.show) {
    document.body.classList.add('overflow-hidden')
    fetchPendingList()
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.body.classList.remove('overflow-hidden')
})
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.28s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.96);
}
</style>
