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
  LexiconContext,
} from '@/types'

export const useMessagesStore = defineStore('messages', () => {
  // State
  const messages = ref<Message[]>([])
  const streamingMessagesMap = ref<Record<string, StreamingMessage>>({})

  // 保持向前兼容的 computed 属性
  const streamingMessage = computed(() =>
    latestRequestedSessionId.value
      ? streamingMessagesMap.value[latestRequestedSessionId.value] ?? null
      : null
  )
  const isStreaming = computed(() => !!streamingMessage.value)
  const isSessionStreaming = (sessionId: string) => !!streamingMessagesMap.value[sessionId]

  const loading = ref(false)
  const error = ref<string | null>(null)
  const latestFetchRequestId = ref(0)  // 2026-03-29 22:55 Asia/Shanghai: 防止会话切换时旧请求覆盖新消息
  const latestRequestedSessionId = ref<string | null>(null)
  const memoryRagMap = ref<Record<string, Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }>>>({})
  const memoryLexiconMap = ref<Record<string, LexiconContext>>({})

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
    streamingMessagesMap.value[sessionId] = {
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
  }

  /**
   * 追加流式内容
   */
  const appendStreamingContent = (sessionId: string, content: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (msg) {
      msg.content += content
    }
  }

  /**
   * 更新流式状态
   */
  const updateStreamingStatus = (sessionId: string, stage: StreamStage, text: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return
    msg.stage = stage
    msg.statusText = text
  }

  /**
   * 更新流式工具调用
   */
  const upsertStreamingToolCall = (sessionId: string, toolCall: StreamToolCall) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return

    const index = msg.toolCalls.findIndex(item => item.id === toolCall.id)
    if (index === -1) {
      msg.toolCalls.push(toolCall)
      return
    }

    msg.toolCalls[index] = {
      ...msg.toolCalls[index],
      ...toolCall
    }
  }

  /**
   * 写入流式工具结果
   */
  const setStreamingToolResult = (sessionId: string, toolCallId: string, content: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return
    msg.toolResults = {
      ...msg.toolResults,
      [toolCallId]: content
    }

    const index = msg.toolCalls.findIndex(item => item.id === toolCallId)
    if (index !== -1) {
      msg.toolCalls[index] = {
        ...msg.toolCalls[index],
        status: 'completed'
      }
    }
  }

  /**
   * 标记流式错误
   */
  const setStreamingError = (sessionId: string, message: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return
    msg.error = message
    msg.isStreaming = false
    msg.statusText = '生成失败'
  }

  /**
   * 完成流式错误消息（不保留过程态信息）
   */
  const finalizeStreamingError = (sessionId: string, payload: {
    id?: string
    created_at?: string
    content: string
  }) => {
    const temp = streamingMessagesMap.value[sessionId]
    if (!temp) return null

    delete streamingMessagesMap.value[sessionId]

    // 仅当前显示的会话才推入视图，防止污染其他会话
    if (sessionId !== latestRequestedSessionId.value) return null

    const finalizedMessage: Message = {
      id: payload.id ?? temp.id,
      session_id: sessionId,
      role: 'assistant',
      content: payload.content,
      created_at: payload.created_at ?? temp.created_at,
      tool_calls: null,
      tool_results: null,
    }

    messages.value.push(finalizedMessage)
    return finalizedMessage
  }

  /**
   * 用户主动停止生成时，保留已生成片段并落定为本地中断消息
   */
  const finalizeStreamingInterrupted = (sessionId: string) => {
    const temp = streamingMessagesMap.value[sessionId]
    if (!temp) return null

    delete streamingMessagesMap.value[sessionId]

    // 仅当前显示的会话才推入视图，防止污染其他会话
    if (sessionId !== latestRequestedSessionId.value) return null

    const interruptedMessage: Message = {
      id: `${temp.id}-interrupted`,
      session_id: sessionId,
      role: 'assistant',
      content: temp.content || '已停止生成',
      created_at: temp.created_at,
      tool_calls: temp.toolCalls.length
        ? JSON.stringify(temp.toolCalls)
        : null,
      tool_results: Object.keys(temp.toolResults).length
        ? JSON.stringify(temp.toolResults)
        : null,
      is_interrupted: true,
    }

    messages.value.push(interruptedMessage)
    return interruptedMessage
  }

  /**
   * 完成流式消息（将临时消息转换为正式消息）
   */
  const completeStreamingMessage = (sessionId: string, payload: FinalizedStreamingMessage = {}) => {
    const temp = streamingMessagesMap.value[sessionId]
    if (!temp) return null

    delete streamingMessagesMap.value[sessionId]

    const finalizedId = payload.id ?? temp.id
    if (finalizedId && temp.ragContext) {
      memoryRagMap.value[finalizedId] = temp.ragContext
    }
    if (finalizedId && temp.lexiconContext) {
      memoryLexiconMap.value[finalizedId] = temp.lexiconContext
    }

    // 仅当前显示的会话才推入视图，防止污染其他会话
    if (sessionId !== latestRequestedSessionId.value) return null

    const finalizedMessage: Message = {
      id: finalizedId,
      session_id: sessionId,
      role: 'assistant',
      content: payload.content ?? temp.content,
      created_at: payload.created_at ?? temp.created_at,
      tool_calls: payload.tool_calls ?? (
        temp.toolCalls.length
          ? JSON.stringify(temp.toolCalls)
          : null
      ),
      tool_results: payload.tool_results ?? (
        Object.keys(temp.toolResults).length
          ? JSON.stringify(temp.toolResults)
          : null
      ),
      rag_context: payload.rag_context ?? temp.ragContext,
      lexicon_context: payload.lexicon_context ?? temp.lexiconContext
    }

    messages.value.push(finalizedMessage)
    return finalizedMessage
  }

  /**
   * 清除流式消息（错误时使用）
   */
  const clearStreamingMessage = (sessionId: string) => {
    delete streamingMessagesMap.value[sessionId]
  }

  /**
   * 清除特定会话的流式（会话删除时使用）
   */
  const clearStreamingForSession = (sessionId: string) => {
    delete streamingMessagesMap.value[sessionId]
  }

  /**
   * 将当前流式消息转为中断挂起状态
   */
  const setStreamingInterrupt = (sessionId: string, questions: QuestionItem[]) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return
    msg.isStreaming = false
    msg.isInterrupted = true
    msg.questions = questions
    msg.statusText = '等待用户确认'
    msg.stage = null
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
    streamingMessage,  // 流式消息临时状态
    isStreaming,  // 是否正在流式输出
    streamingMessagesMap, // 🆕 新增 Map 状态导出
    loading,
    error,
    // Actions
    fetchMessages,
    createMessage,
    deleteMessage,
    submitMessageFeedback,
    clearMessages,
    // 流式消息管理
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
    clearStreamingForSession, // 🆕 新增清理 action
    setStreamingInterrupt,
    displayMessages,
    isSessionStreaming,  // 🆕 新增会话状态判断 getter
    memoryRagMap,
    memoryLexiconMap,
  }
})
