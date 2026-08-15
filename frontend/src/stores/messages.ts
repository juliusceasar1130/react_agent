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
  SubagentSessionState,
} from '@/types'
import { useRequestGuard } from '@/composables/useRequestGuard'
import { formatSubagentTitle, parseJson } from '@/utils/helpers'

/** 过滤系统内部上下文标记，防止泄露到用户界面 */
const INTERNAL_MARKER_RE = /<context_(?:redacted|collapsed)[^>]*\/>/g
const stripInternalMarkers = (text: string): string =>
  text.replace(INTERNAL_MARKER_RE, '')

/** 从持久化的 tool_calls 和 tool_results 中无损重构子智能体卡片数据 */
const reconstructSubagents = (
  toolCallsJson: string | null | undefined,
  toolResultsJson: string | null | undefined
): Record<string, SubagentSessionState> | undefined => {
  if (!toolCallsJson) return undefined
  try {
    const parsed = JSON.parse(toolCallsJson)
    if (!Array.isArray(parsed)) return undefined
    let toolResults: Record<string, string> = {}
    if (toolResultsJson) {
      try {
        toolResults = JSON.parse(toolResultsJson)
      } catch {
        toolResults = {}
      }
    }

    const subagents: Record<string, SubagentSessionState> = {}
    for (const tool of parsed) {
      if (tool && tool.subagent_id) {
        const subId = tool.subagent_id
        if (!subagents[subId]) {
          const name = tool.subagent_name || 'sql_domain_agent'
          const title = formatSubagentTitle(name)
          subagents[subId] = {
            id: subId,
            name,
            title,
            status: 'completed',
            reasoningText: '',
            toolCalls: [],
            toolResults: {},
            content: '',
          }
        }
        subagents[subId].toolCalls.push(tool)
        if (toolResults[tool.id]) {
          subagents[subId].toolResults[tool.id] = toolResults[tool.id]
        }
      }
    }
    return Object.keys(subagents).length > 0 ? subagents : undefined
  } catch {
    return undefined
  }
}

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
  const memorySubagentsMap = ref<Record<string, Record<string, SubagentSessionState>>>({})

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

      messages.value = fetchedMessages.map((msg) => {
        // 后端返回的 subagents 为 JSON 字符串，解析为对象；
        // 旧数据（无 subagents 列）走 tool_calls 兜底重构（仅工具链）
        const rawSubagents = (msg as { subagents?: unknown }).subagents
        const subagentsObj = typeof rawSubagents === 'string'
          ? (parseJson<Record<string, SubagentSessionState>>(rawSubagents) ?? undefined)
          : (rawSubagents as Record<string, SubagentSessionState> | undefined)
        if (subagentsObj) {
          return {
            ...msg,
            subagents: subagentsObj,
          }
        }
        if (msg.tool_calls) {
          const reconstructed = reconstructSubagents(msg.tool_calls, msg.tool_results)
          if (reconstructed) {
            return {
              ...msg,
              subagents: reconstructed,
            }
          }
        }
        return msg
      })
      return messages.value
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
   * 辅助方法：确保 subagent 会话状态对象已初始化
   */
  const ensureSubagentState = (
    msg: StreamingMessage,
    subagentId: string,
    subagentName?: string
  ): SubagentSessionState => {
    if (!msg.subagents) {
      msg.subagents = {}
    }
    if (!msg.subagents[subagentId]) {
      const name = subagentName || 'sql_domain_agent'
      const title = formatSubagentTitle(name)
      msg.subagents[subagentId] = {
        id: subagentId,
        name,
        title,
        status: 'running',
        reasoningText: '',
        toolCalls: [],
        toolResults: {},
        content: ''
      }
    }
    return msg.subagents[subagentId]
  }

  /**
   * 追加流式内容
   */
  const appendStreamingContent = (
    sessionId: string,
    content: string,
    subagentId?: string,
    subagentName?: string
  ) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (msg) {
      if (subagentId) {
        const subagent = ensureSubagentState(msg, subagentId, subagentName)
        subagent.content = stripInternalMarkers((subagent.content || '') + content)
        return
      }

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
  const appendStreamingReasoning = (
    sessionId: string,
    text: string,
    subagentId?: string,
    subagentName?: string
  ) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (msg) {
      const now = Date.now()
      if (subagentId) {
        const subagent = ensureSubagentState(msg, subagentId, subagentName)
        if (!subagent.reasoningStartTime) {
          subagent.reasoningStartTime = now
        }
        subagent.reasoningEndTime = now
        const startTimeRef = subagent.reasoningStartTime || now
        subagent.reasoningDuration = Math.max(0.1, (now - startTimeRef) / 1000)
        subagent.reasoningText = (subagent.reasoningText || '') + text
        return
      }

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

    if (toolCall.subagent_id) {
      const subagent = ensureSubagentState(msg, toolCall.subagent_id, toolCall.subagent_name)
      const index = subagent.toolCalls.findIndex(item => item.id === toolCall.id)
      if (index === -1) {
        subagent.toolCalls.push(toolCall)
      } else {
        subagent.toolCalls[index] = {
          ...subagent.toolCalls[index],
          ...toolCall
        }
      }
      return
    }

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
  const setStreamingToolResult = (
    sessionId: string,
    toolCallId: string,
    content: string,
    subagentId?: string,
    subagentName?: string
  ) => {
    const msg = streamingMessagesMap.value[sessionId]
    if (!msg) return
    msg.needsReasoningSeparator = true

    if (subagentId) {
      const subagent = ensureSubagentState(msg, subagentId, subagentName)
      subagent.toolResults = {
        ...subagent.toolResults,
        [toolCallId]: content
      }
      const index = subagent.toolCalls.findIndex(item => item.id === toolCallId)
      if (index !== -1) {
        subagent.toolCalls[index] = {
          ...subagent.toolCalls[index],
          status: 'completed'
        }
      }
      return
    }

    // 检查是否属于某个子智能体
    if (msg.subagents) {
      for (const sub of Object.values(msg.subagents)) {
        const index = sub.toolCalls.findIndex(item => item.id === toolCallId)
        if (index !== -1) {
          sub.toolResults = {
            ...sub.toolResults,
            [toolCallId]: content
          }
          sub.toolCalls[index] = {
            ...sub.toolCalls[index],
            status: 'completed'
          }
          return
        }
      }
    }

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
   * 完成流式错误消息（保留子智能体过程态信息）
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

    if (temp.subagents) {
      for (const sub of Object.values(temp.subagents)) {
        if (sub.status === 'running') {
          sub.status = 'error'
          sub.error = payload.content
        }
      }
    }

    const finalizedMessage: Message = {
      id: payload.id ?? temp.id,
      session_id: sessionId,
      role: 'assistant',
      content: payload.content,
      created_at: payload.created_at ?? temp.created_at,
      tool_calls: null,
      tool_results: null,
      subagents: temp.subagents
    }

    messages.value.push(finalizedMessage)
    if (temp.subagents) {
      memorySubagentsMap.value[finalizedMessage.id] = temp.subagents
    }
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

    if (temp.subagents) {
      for (const sub of Object.values(temp.subagents)) {
        if (sub.status === 'running') {
          sub.status = 'interrupted'
        }
      }
    }

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
      subagents: temp.subagents,
    }

    if (temp.reasoningText) {
      memoryReasoningMap.value[interruptedMessage.id] = temp.reasoningText
    }
    if (duration !== undefined) {
      memoryReasoningDurationMap.value[interruptedMessage.id] = duration
    }
    if (temp.subagents) {
      memorySubagentsMap.value[interruptedMessage.id] = temp.subagents
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

    if (temp.subagents) {
      for (const sub of Object.values(temp.subagents)) {
        if (sub.status === 'running') {
          sub.status = 'completed'
        }
      }
    }

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
    if (finalizedId && (payload.subagents || temp.subagents)) {
      memorySubagentsMap.value[finalizedId] = payload.subagents ?? temp.subagents!
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
      tool_artifact: payload.tool_artifact ?? temp.tool_artifact,
      subagents: payload.subagents ?? temp.subagents,
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
    memorySubagentsMap,
  }
})
