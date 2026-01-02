import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMessagesBySessionApi, createMessageApi, deleteMessageApi } from '@/api/messages'
import type { Message, MessageCreate, StreamingMessage } from '@/types'

export const useMessagesStore = defineStore('messages', () => {
  // State
  const messages = ref<Message[]>([])
  const streamingMessage = ref<StreamingMessage | null>(null)  // 流式消息临时状态 - 2025-01-01
  const isStreaming = ref(false)  // 是否正在流式输出 - 2025-01-01
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Actions
  const fetchMessages = async (sessionId: string) => {
    loading.value = true
    error.value = null
    try {
      messages.value = await getMessagesBySessionApi(sessionId)
    } catch (err) {
      error.value = '加载消息失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createMessage = async (data: MessageCreate) => {
    loading.value = true
    error.value = null
    try {
      const newMessage = await createMessageApi(data)
      messages.value.push(newMessage)
      return newMessage
    } catch (err) {
      error.value = '创建消息失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteMessage = async (messageId: string) => {
    loading.value = true
    error.value = null
    try {
      await deleteMessageApi(messageId)
      messages.value = messages.value.filter(m => m.id !== messageId)
    } catch (err) {
      error.value = '删除消息失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearMessages = () => {
    messages.value = []
  }

  // 流式消息管理 - 2025-01-01

  /**
   * 开始流式消息（创建临时消息对象）
   */
  const startStreamingMessage = (sessionId: string) => {
    const tempId = `temp-${Date.now()}`
    streamingMessage.value = {
      id: tempId,
      session_id: sessionId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: new Date()
    }
    isStreaming.value = true
  }

  /**
   * 追加流式内容
   */
  const appendStreamingContent = (content: string) => {
    if (streamingMessage.value) {
      streamingMessage.value.content += content
    }
  }

  /**
   * 完成流式消息（将临时消息转换为正式消息）
   */
  const completeStreamingMessage = (fullMessage: Message) => {
    messages.value.push(fullMessage)
    streamingMessage.value = null
    isStreaming.value = false
  }

  /**
   * 清除流式消息（错误时使用）
   */
  const clearStreamingMessage = () => {
    streamingMessage.value = null
    isStreaming.value = false
  }

  /**
   * 显示消息列表（包含流式临时消息）
   */
  const displayMessages = computed(() => {
    if (streamingMessage.value) {
      return [...messages.value, streamingMessage.value]
    }
    return messages.value
  })

  return {
    // State
    messages,
    streamingMessage,  // 流式消息临时状态 - 2025-01-01
    isStreaming,  // 是否正在流式输出 - 2025-01-01
    loading,
    error,
    // Actions
    fetchMessages,
    createMessage,
    deleteMessage,
    clearMessages,
    // 流式消息管理 - 2025-01-01
    startStreamingMessage,
    appendStreamingContent,
    completeStreamingMessage,
    clearStreamingMessage,
    displayMessages,  // 包含流式临时消息的列表
  }
})
