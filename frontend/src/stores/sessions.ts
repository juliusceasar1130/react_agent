import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createSessionApi, getSessionsApi, updateSessionApi, deleteSessionApi } from '@/api/sessions'
import type { Session, SessionCreate } from '@/types'
import { useMessagesStore } from './messages'
import { useRequestGuard } from '@/composables/useRequestGuard'
import { abortSessionStream } from '@/composables/useChatStream'  // 2026-08-30: 删除会话前中止关联流（运行时调用，循环引用安全）

export const useSessionsStore = defineStore('sessions', () => {
  // State
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const fetchGuard = useRequestGuard()  // 防竞态：快速切换时丢弃过期响应

  // Getters
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) || null
  )

  // Actions
  const fetchSessions = async () => {
    const requestId = fetchGuard.next()
    loading.value = true
    error.value = null
    try {
      const result = await getSessionsApi()
      if (!fetchGuard.isFresh(requestId)) return
      sessions.value = result
    } catch (err: any) {
      if (!fetchGuard.isFresh(requestId)) return
      error.value = err.message || '加载会话失败'
      throw err
    } finally {
      if (fetchGuard.isFresh(requestId)) {
        loading.value = false
      }
    }
  }

  const createSession = async (data: SessionCreate) => {
    loading.value = true
    error.value = null
    try {
      const newSession = await createSessionApi(data)
      sessions.value.unshift(newSession)
      currentSessionId.value = newSession.id
      return newSession
    } catch (err: any) {
      error.value = err.message || '创建会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateSession = async (id: string, data: Partial<SessionCreate>) => {
    loading.value = true
    error.value = null
    try {
      const updated = await updateSessionApi(id, data)
      const index = sessions.value.findIndex(s => s.id === id)
      if (index !== -1) {
        sessions.value[index] = updated
      }
      return updated
    } catch (err: any) {
      error.value = err.message || '更新会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteSession = async (id: string) => {
    // 2026-08-30: 若该会话有活跃流，先中止底层 SSE 连接，避免后台空跑浪费服务端算力
    abortSessionStream(id)
    loading.value = true
    error.value = null
    try {
      await deleteSessionApi(id)
      sessions.value = sessions.value.filter(s => s.id !== id)
      if (currentSessionId.value === id) {
        currentSessionId.value = null
        // 清空消息列表 - 2025-01-01
        const messagesStore = useMessagesStore()
        messagesStore.clearMessages()
      }
    } catch (err: any) {
      error.value = err.message || '删除会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const setCurrentSession = (id: string) => {
    currentSessionId.value = id
  }

  return {
    // State
    sessions,
    currentSessionId,
    loading,
    error,
    // Getters
    currentSession,
    // Actions
    fetchSessions,
    createSession,
    updateSession,
    deleteSession,
    setCurrentSession,
  }
})
