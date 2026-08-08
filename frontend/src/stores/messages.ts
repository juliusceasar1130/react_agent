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
  ToolArtifact,
} from '@/types'
import { useRequestGuard } from '@/composables/useRequestGuard'

/** 过滤系统内部上下文标记，防止泄露到用户界面 */
const INTERNAL_MARKER_RE = /<context_(?:redacted|collapsed)[^>]*\/>/g
const stripInternalMarkers = (text: string): string =>
  text.replace(INTERNAL_MARKER_RE, '')

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
  const fetchGuard = useRequestGuard()  // 2026-03-29 22:55 Asia/Shanghai: 防止会话切换时旧请求覆盖新消息
  const latestRequestedSessionId = ref<string | null>(null)
  const memoryRagMap = ref<Record<string, Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }>>>({})
  const memoryLexiconMap = ref<Record<string, LexiconContext>>({})
  const memoryArtifactMap = ref<Record<string, ToolArtifact>>({})
  const memoryReasoningMap = ref<Record<string, string>>({})
  const memoryReasoningDurationMap = ref<Record<string, number>>({})

  // Actions
  const fetchMessages = async (sessionId: string) => {
    const requestId = fetchGuard.next()
    latestRequestedSessionId.value = sessionId
    loading.value = true
    error.value = null
    try {
      const fetchedMessages = await getMessagesBySessionApi(sessionId)
      if (
        !fetchGuard.isFresh(requestId)
        || latestRequestedSessionId.value !== sessionId
      ) {
        return null
      }

      messages.value = fetchedMessages
      return fetchedMessages
    } catch (err: any) {
      if (!fetchGuard.isFresh(requestId)) {
        return null
      }
      error.value = err.message || '加载消息失败'
      throw err
    } finally {
      if (fetchGuard.isFresh(requestId)) {
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
    } catch (err: any) {
      error.value = err.message || '创建消息失败'
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
    } catch (err: any) {
      error.value = err.message || '删除消息失败'
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
    fetchGuard.next()
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
      requestStartTime: Date.now(),
      error: null
    }
  }

  /**
   * 追加流式内容
   */
  const appendStreamingContent = (sessionId: string, content: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (msg) {
      if (msg.requestStartTime && !msg.thinkingEnded) {
        msg.thinkingEnded = true
        msg.reasoningEndTime = Date.now()
        msg.reasoningDuration = Math.max(0.1, (msg.reasoningEndTime - msg.requestStartTime) / 1000)
      }
      msg.content = stripInternalMarkers(msg.content + content)
    }
  }

  /**
   * 追加流式思考内容
   */
  const appendStreamingReasoning = (sessionId: string, text: string) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (msg) {
      const now = Date.now()
      if (!msg.reasoningStartTime) {
        msg.reasoningStartTime = now
      }
      msg.reasoningEndTime = now
      const startTimeRef = msg.requestStartTime || msg.reasoningStartTime || now
      msg.reasoningDuration = Math.max(0.1, (now - startTimeRef) / 1000)

      if (msg.reasoningText && msg.needsReasoningSeparator) {
        const trimmed = msg.reasoningText.trimEnd()
        const isSentenceEnd = /[。！？;\n:]$/.test(trimmed)
        if (isSentenceEnd && !msg.reasoningText.endsWith('\n')) {
          msg.reasoningText += '\n\n'
        } else if (!isSentenceEnd && /[a-zA-Z0-9]$/.test(trimmed) && /^[a-zA-Z0-9]/.test(text)) {
          msg.reasoningText += ' '
        }
        msg.needsReasoningSeparator = false
      }

      msg.reasoningText = (msg.reasoningText || '') + text
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
    msg.needsReasoningSeparator = true

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
    msg.needsReasoningSeparator = true
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

    const startTimeRef = temp.requestStartTime || temp.reasoningStartTime
    const duration = temp.reasoningDuration || (
      startTimeRef
        ? Math.max(0.1, ((temp.reasoningEndTime || Date.now()) - startTimeRef) / 1000)
        : undefined
    )

    const interruptedMessage: Message = {
      id: `${temp.id}-interrupted`,
      session_id: sessionId,
      role: 'assistant',
      content: temp.content || '已停止生成',
      reasoningText: temp.reasoningText,
      reasoningDuration: duration,
      created_at: temp.created_at,
      tool_calls: temp.toolCalls.length
        ? JSON.stringify(temp.toolCalls)
        : null,
      tool_results: Object.keys(temp.toolResults).length
        ? JSON.stringify(temp.toolResults)
        : null,
      is_interrupted: true,
    }

    if (temp.reasoningText) {
      memoryReasoningMap.value[interruptedMessage.id] = temp.reasoningText
    }
    if (duration !== undefined) {
      memoryReasoningDurationMap.value[interruptedMessage.id] = duration
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
    const startTimeRef = temp.requestStartTime || temp.reasoningStartTime
    const duration = temp.reasoningDuration || (
      startTimeRef
        ? Math.max(0.1, ((temp.reasoningEndTime || Date.now()) - startTimeRef) / 1000)
        : undefined
    )

    if (finalizedId && temp.ragContext) {
      memoryRagMap.value[finalizedId] = temp.ragContext
    }
    if (finalizedId && temp.lexiconContext) {
      memoryLexiconMap.value[finalizedId] = temp.lexiconContext
    }
    if (finalizedId && temp.tool_artifact) {
      memoryArtifactMap.value[finalizedId] = temp.tool_artifact
    }
    if (finalizedId && temp.reasoningText) {
      memoryReasoningMap.value[finalizedId] = temp.reasoningText
    }
    if (finalizedId && duration !== undefined) {
      memoryReasoningDurationMap.value[finalizedId] = duration
    }

    // 仅当前显示的会话才推入视图，防止污染其他会话
    if (sessionId !== latestRequestedSessionId.value) return null

    const finalizedMessage: Message = {
      id: finalizedId,
      session_id: sessionId,
      role: 'assistant',
      content: stripInternalMarkers(payload.content ?? temp.content),
      reasoningText: temp.reasoningText,
      reasoningDuration: duration,
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
      lexicon_context: payload.lexicon_context ?? temp.lexiconContext,
      tool_artifact: payload.tool_artifact ?? temp.tool_artifact
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
    streamingMessagesMap, // Map 状态导出
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
    appendStreamingReasoning,
    updateStreamingStatus,
    upsertStreamingToolCall,
    setStreamingToolResult,
    finalizeStreamingError,
    finalizeStreamingInterrupted,
    completeStreamingMessage,
    clearStreamingMessage,
    setStreamingInterrupt,
    displayMessages,
    isSessionStreaming, // 会话状态判断 getter
    memoryRagMap,
    memoryLexiconMap,
    memoryArtifactMap,
    memoryReasoningMap,
    memoryReasoningDurationMap,
  }
})
