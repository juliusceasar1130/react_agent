import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createSessionApi, getSessionsApi, updateSessionApi, deleteSessionApi } from '@/api/sessions'
import type { Session, SessionCreate } from '@/types'
import { useMessagesStore } from './messages'  // 新增 - 2025-01-01

export const useSessionsStore = defineStore('sessions', () => {
  // State
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value) || null
  )

  // Actions
  const fetchSessions = async () => {
    loading.value = true
    error.value = null
    try {
      sessions.value = await getSessionsApi()
    } catch (err) {
      error.value = '加载会话失败'
      throw err
    } finally {
      loading.value = false
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
    } catch (err) {
      error.value = '创建会话失败'
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
    } catch (err) {
      error.value = '更新会话失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteSession = async (id: string) => {
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
    } catch (err) {
      error.value = '删除会话失败'
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
