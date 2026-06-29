import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMessagesBySessionApi, createMessageApi, deleteMessageApi, submitMessageFeedbackApi } from '@/api/messages'
import type {
  FinalizedStreamingMessage,
  Message,
  MessageCreate,
  StreamStage,
  StreamingMessage,
  StreamToolCall,
  QuestionItem,
} from '@/types'

export const useMessagesStore = defineStore('messages', () => {
  // State
  const messages = ref<Message[]>([])
  const streamingMessage = ref<StreamingMessage | null>(null)  // 流式消息临时状态 - 2025-01-01
  const isStreaming = ref(false)  // 是否正在流式输出 - 2025-01-01
  const loading = ref(false)
  const error = ref<string | null>(null)
  const latestFetchRequestId = ref(0)  // 2026-03-29 22:55 Asia/Shanghai: 防止会话切换时旧请求覆盖新消息
  const latestRequestedSessionId = ref<string | null>(null)

  // Actions
  const fetchMessages = async (sessionId: string) => {
    const requestId = latestFetchRequestId.value + 1
    latestFetchRequestId.value = requestId
    latestRequestedSessionId.value = sessionId
    loading.value = true
    error.value = null
    try {
      const fetchedMessages = await getMessagesBySessionApi(sessionId)
      if (
        requestId !== latestFetchRequestId.value
        || latestRequestedSessionId.value !== sessionId
      ) {
        return null
      }

      messages.value = fetchedMessages
      return fetchedMessages
    } catch (err) {
      if (requestId !== latestFetchRequestId.value) {
        return null
      }
      error.value = '加载消息失败'
      throw err
    } finally {
      if (requestId === latestFetchRequestId.value) {
        loading.value = false
      }
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

  const submitMessageFeedback = async (messageId: string, feedback: 'none' | 'like' | 'dislike' | 'collected' | 'approved') => {
    try {
      const updatedMessage = await submitMessageFeedbackApi(messageId, feedback)
      const index = messages.value.findIndex(m => m.id === messageId)
      if (index !== -1) {
        messages.value[index] = { ...messages.value[index], feedback: updatedMessage.feedback }
      }
    } catch (err) {
      console.error('提交消息反馈失败', err)
      throw err
    }
  }

  const clearMessages = () => {
    latestFetchRequestId.value += 1
    latestRequestedSessionId.value = null
    messages.value = []
  }

  // 流式消息管理 - 2025-01-01

  /**
   * 开始流式消息（创建临时消息对象）
   */
  const startStreamingMessage = (sessionId: string) => {
    const now = new Date().toISOString()
    const tempId = `temp-${Date.now()}`
    streamingMessage.value = {
      id: tempId,
      session_id: sessionId,
      role: 'assistant',
      content: '',
      created_at: now,
      isStreaming: true,
      statusText: '正在分析问题',
      stage: 'thinking',
      toolCalls: [],
      toolResults: {},
      error: null
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
   * 更新流式状态
   */
  const updateStreamingStatus = (stage: StreamStage, text: string) => {
    if (!streamingMessage.value) return
    streamingMessage.value.stage = stage
    streamingMessage.value.statusText = text
  }

  /**
   * 更新流式工具调用
   */
  const upsertStreamingToolCall = (toolCall: StreamToolCall) => {
    if (!streamingMessage.value) return

    const index = streamingMessage.value.toolCalls.findIndex(item => item.id === toolCall.id)
    if (index === -1) {
      streamingMessage.value.toolCalls.push(toolCall)
      return
    }

    streamingMessage.value.toolCalls[index] = {
      ...streamingMessage.value.toolCalls[index],
      ...toolCall
    }
  }

  /**
   * 写入流式工具结果
   */
  const setStreamingToolResult = (toolCallId: string, content: string) => {
    if (!streamingMessage.value) return
    streamingMessage.value.toolResults = {
      ...streamingMessage.value.toolResults,
      [toolCallId]: content
    }

    const index = streamingMessage.value.toolCalls.findIndex(item => item.id === toolCallId)
    if (index !== -1) {
      streamingMessage.value.toolCalls[index] = {
        ...streamingMessage.value.toolCalls[index],
        status: 'completed'
      }
    }
  }

  /**
   * 标记流式错误
   */
  const setStreamingError = (message: string) => {
    if (!streamingMessage.value) return
    streamingMessage.value.error = message
    streamingMessage.value.isStreaming = false
    streamingMessage.value.statusText = '生成失败'
    isStreaming.value = false
  }

  /**
   * 完成流式错误消息（不保留过程态信息）
   */
  const finalizeStreamingError = (payload: {
    id?: string
    created_at?: string
    content: string
  }) => {
    if (!streamingMessage.value) return null

    const finalizedMessage: Message = {
      id: payload.id ?? streamingMessage.value.id,
      session_id: streamingMessage.value.session_id,
      role: 'assistant',
      content: payload.content,
      created_at: payload.created_at ?? streamingMessage.value.created_at,
      tool_calls: null,
      tool_results: null,
    }

    messages.value.push(finalizedMessage)
    streamingMessage.value = null
    isStreaming.value = false
    return finalizedMessage
  }

  /**
   * 用户主动停止生成时，保留已生成片段并落定为本地中断消息
   */
  const finalizeStreamingInterrupted = () => {
    if (!streamingMessage.value) return null

    const interruptedMessage: Message = {
      id: `${streamingMessage.value.id}-interrupted`,
      session_id: streamingMessage.value.session_id,
      role: 'assistant',
      content: streamingMessage.value.content || '已停止生成',
      created_at: streamingMessage.value.created_at,
      tool_calls: streamingMessage.value.toolCalls.length
        ? JSON.stringify(streamingMessage.value.toolCalls)
        : null,
      tool_results: Object.keys(streamingMessage.value.toolResults).length
        ? JSON.stringify(streamingMessage.value.toolResults)
        : null,
      is_interrupted: true,
    }

    messages.value.push(interruptedMessage)
    streamingMessage.value = null
    isStreaming.value = false
    return interruptedMessage
  }

  /**
   * 完成流式消息（将临时消息转换为正式消息）
   */
  const completeStreamingMessage = (payload: FinalizedStreamingMessage = {}) => {
    if (!streamingMessage.value) return null

    const finalizedMessage: Message = {
      id: payload.id ?? streamingMessage.value.id,
      session_id: streamingMessage.value.session_id,
      role: 'assistant',
      content: payload.content ?? streamingMessage.value.content,
      created_at: payload.created_at ?? streamingMessage.value.created_at,
      tool_calls: payload.tool_calls ?? (
        streamingMessage.value.toolCalls.length
          ? JSON.stringify(streamingMessage.value.toolCalls)
          : null
      ),
      tool_results: payload.tool_results ?? (
        Object.keys(streamingMessage.value.toolResults).length
          ? JSON.stringify(streamingMessage.value.toolResults)
          : null
      )
    }

    messages.value.push(finalizedMessage)
    streamingMessage.value = null
    isStreaming.value = false
    return finalizedMessage
  }

  /**
   * 清除流式消息（错误时使用）
   */
  const clearStreamingMessage = () => {
    streamingMessage.value = null
    isStreaming.value = false
  }

  /**
   * 将当前流式消息转为中断挂起状态
   */
  const setStreamingInterrupt = (questions: QuestionItem[]) => {
    if (!streamingMessage.value) return
    streamingMessage.value.isStreaming = false
    streamingMessage.value.isInterrupted = true
    streamingMessage.value.questions = questions
    streamingMessage.value.statusText = '等待用户确认'
    streamingMessage.value.stage = null
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
    submitMessageFeedback,
    clearMessages,
    // 流式消息管理 - 2025-01-01
    startStreamingMessage,
    appendStreamingContent,
    updateStreamingStatus,
    upsertStreamingToolCall,
    setStreamingToolResult,
    setStreamingError,
    finalizeStreamingError,
    finalizeStreamingInterrupted,
    completeStreamingMessage,
    clearStreamingMessage,
    setStreamingInterrupt,
    displayMessages,  // 包含流式临时消息的列表
  }
})
