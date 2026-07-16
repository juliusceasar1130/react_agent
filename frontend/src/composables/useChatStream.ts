// 流式聊天逻辑封装
// 创建日期: 2025-01-01
// 修改时间: 2026-03-27 17:42 Asia/Shanghai
// 主要修改内容:
// - 改为结构化 StreamEvent 驱动
// - 实现本地完成落定 + 后台静默同步
// - 2026-03-27 22:12 Asia/Shanghai: 错误场景直接落定为最终消息，避免残留过程态
// - 2026-03-29 22:35 Asia/Shanghai: 发送失败后追加一次服务端消息同步，避免已持久化的用户消息在前端被误回滚
// - 2026-03-29 22:55 Asia/Shanghai: 改为以服务端会话状态为准，并避免切换会话后旧同步覆盖当前消息
// - 2026-03-29 23:10 Asia/Shanghai: 新增流式请求取消能力，支持“停止生成”
// - 2026-03-31 21:31 Asia/Shanghai: 移除宽松事件兜底，改为穷尽式处理统一 SSE 事件协议
// - 2026-03-31 22:15 Asia/Shanghai: 停止生成后保留已生成片段，并明确落定为本地“已停止生成”消息

import { ref, watch } from 'vue'
import { sendChatStream, sendChatMessage, sendChatResumeStream } from '@/api/chat'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import type { ContextWarningPayload, Message, StreamEvent, StreamToolCall } from '@/types'

const assertNever = (value: never): never => {
  throw new Error(`未处理的流式事件: ${JSON.stringify(value)}`)
}

/**
 * 流式聊天 Composable
 * 封装流式和非流式消息发送逻辑
 */
export function useChatStream() {
  const messagesStore = useMessagesStore()
  const sessionsStore = useSessionsStore()

  const isSending = ref(false)
  const streamMode = ref(true)  // 流式模式开关状态
  const enableThinking = ref(false) // 新增：思考模式开关状态，默认关闭
  const activeStreamController = ref<AbortController | null>(null)
  const contextWarning = ref<ContextWarningPayload | null>(null)

  watch(
    () => sessionsStore.currentSessionId,
    () => {
      contextWarning.value = null
    }
  )

  const syncMessagesIfCurrent = (sessionId: string) => {
    if (sessionsStore.currentSessionId !== sessionId) {
      return
    }

    void messagesStore.fetchMessages(sessionId).catch((error) => {
      console.error('消息同步失败:', error)
    })
  }

  const syncSessions = async () => {
    try {
      await sessionsStore.fetchSessions()
    } catch (error) {
      console.error('会话同步失败:', error)
    }
  }

  const isAbortError = (error: unknown) =>
    error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError'

  const stopStreaming = () => {
    activeStreamController.value?.abort()
  }

  /**
   * 发送消息（根据 streamMode 选择流式或非流式）
   */
  const sendMessage = async (content: string) => {
    const currentSession = sessionsStore.currentSession
    if (!currentSession) {
      throw new Error('没有选择会话')
    }

    isSending.value = true
    contextWarning.value = null

    // 1. 立即显示用户消息（乐观更新）- 2025-01-01
    const tempUserMessage: Message = {
      id: `temp-user-${Date.now()}`,
      session_id: currentSession.id,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    }
    // Pinia setup store 中 ref 会自动解包，所以不需要 .value
    messagesStore.messages.push(tempUserMessage)

    try {
      // 2. 根据模式调用后端
      if (streamMode.value) {
        // 流式处理
        await handleStreamMessage(currentSession.id, content)
      } else {
        // 非流式处理
        await handleNormalMessage(currentSession.id, content)
      }
    } catch (error) {
      if (isAbortError(error)) {
        console.info('流式请求已取消')
        messagesStore.finalizeStreamingInterrupted()
        void syncSessions()
        return
      }

      console.error('发送消息失败:', error)
      console.error('[diagnose] 流式请求异常类型:', (error as Error)?.constructor?.name, 'message:', (error as Error)?.message)
      // 发送失败时移除临时用户消息 - 2025-01-01
      const index = messagesStore.messages.findIndex(m => m.id === tempUserMessage.id)
      if (index !== -1) {
        messagesStore.messages.splice(index, 1)
      }
      messagesStore.clearStreamingMessage()
      syncMessagesIfCurrent(currentSession.id)
      void syncSessions()
      throw error
    } finally {
      isSending.value = false
    }
  }

  /**
   * 处理流式消息
   */
  const handleStreamMessage = async (sessionId: string, content: string) => {
    let hasTerminalEvent = false
    const controller = new AbortController()
    activeStreamController.value = controller

    // 开始流式消息（创建临时消息对象）
    messagesStore.startStreamingMessage(sessionId)

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'token':
          if (event.text) {
            messagesStore.appendStreamingContent(event.text)
          }
          return

        case 'status':
          if (event.source === 'context_warning' && event.detail) {
            contextWarning.value = event.detail as unknown as ContextWarningPayload
            return
          }
          messagesStore.updateStreamingStatus(event.stage, event.text)
          return

        case 'tool_call':
          messagesStore.upsertStreamingToolCall({
            id: event.id,
            name: event.name,
            args_text: event.args_text,
            status: event.status,
          } satisfies StreamToolCall)
          return

        case 'tool_result':
          messagesStore.setStreamingToolResult(event.id, event.content)
          return

        case 'rag_context':
          if (messagesStore.streamingMessage) {
            messagesStore.streamingMessage.ragContext = event.rag_context
          }
          return

        case 'lexicon_context':
          if (messagesStore.streamingMessage) {
            messagesStore.streamingMessage.lexiconContext = event.lexicon_context
          }
          return

        case 'final':
          hasTerminalEvent = true
          messagesStore.completeStreamingMessage({
            id: event.message_id,
            created_at: event.created_at,
            content: event.content,
            tool_calls: event.tool_calls ? JSON.stringify(event.tool_calls) : null,
            tool_results: event.tool_results ? JSON.stringify(event.tool_results) : null,
          })
          syncMessagesIfCurrent(sessionId)
          void syncSessions()
          return

        case 'error':
          hasTerminalEvent = true
          messagesStore.finalizeStreamingError({
            id: event.message_id,
            created_at: event.created_at,
            content: event.message,
          })
          syncMessagesIfCurrent(sessionId)
          void syncSessions()
          return

        case 'interrupt':
          hasTerminalEvent = true
          messagesStore.setStreamingInterrupt(event.questions)
          syncMessagesIfCurrent(sessionId)
          void syncSessions()
          return
      }

      assertNever(event)
    }

    try {
      await sendChatStream(
        { 
          message: content, 
          session_id: sessionId, 
          stream: true,
          enable_thinking: enableThinking.value // 新增透传
        },
        handleEvent,
        { signal: controller.signal }
      )

      if (!hasTerminalEvent) {
        throw new Error('流式响应未正常结束')
      }
    } finally {
      if (activeStreamController.value === controller) {
        activeStreamController.value = null
      }
    }
  }

  /**
   * 处理非流式消息
   */
  const handleNormalMessage = async (sessionId: string, content: string) => {
    const response = await sendChatMessage({
      message: content,
      session_id: sessionId,
      stream: false,
      enable_thinking: enableThinking.value // 新增透传
    })
    contextWarning.value = response.context_warning ?? null

    // 非流式完成后，重新加载消息列表
    if (sessionsStore.currentSessionId === sessionId) {
      await messagesStore.fetchMessages(sessionId)
    }
    await syncSessions()
  }

  /**
   * 恢复挂起的中断消息
   */
  const resumeMessage = async (answers: Record<string, string | string[]>) => {
    const currentSession = sessionsStore.currentSession
    if (!currentSession) {
      throw new Error('没有选择会话')
    }

    isSending.value = true
    contextWarning.value = null

    // 重新将临时消息的 isStreaming 设为 true，并清除 isInterrupted 状态
    if (messagesStore.streamingMessage) {
      messagesStore.streamingMessage.isStreaming = true
      messagesStore.streamingMessage.isInterrupted = false
      messagesStore.streamingMessage.statusText = '恢复会话生成中'
    }
    messagesStore.isStreaming = true

    let hasTerminalEvent = false
    const controller = new AbortController()
    activeStreamController.value = controller

    const handleEvent = (event: StreamEvent) => {
      switch (event.type) {
        case 'token':
          if (event.text) {
            messagesStore.appendStreamingContent(event.text)
          }
          return

        case 'status':
          if (event.source === 'context_warning' && event.detail) {
            contextWarning.value = event.detail as unknown as ContextWarningPayload
            return
          }
          messagesStore.updateStreamingStatus(event.stage, event.text)
          return

        case 'tool_call':
          messagesStore.upsertStreamingToolCall({
            id: event.id,
            name: event.name,
            args_text: event.args_text,
            status: event.status,
          } satisfies StreamToolCall)
          return

        case 'tool_result':
          messagesStore.setStreamingToolResult(event.id, event.content)
          return

        case 'rag_context':
          if (messagesStore.streamingMessage) {
            messagesStore.streamingMessage.ragContext = event.rag_context
          }
          return

        case 'lexicon_context':
          if (messagesStore.streamingMessage) {
            messagesStore.streamingMessage.lexiconContext = event.lexicon_context
          }
          return

        case 'final':
          hasTerminalEvent = true
          messagesStore.completeStreamingMessage({
            id: event.message_id,
            created_at: event.created_at,
            content: event.content,
            tool_calls: event.tool_calls ? JSON.stringify(event.tool_calls) : null,
            tool_results: event.tool_results ? JSON.stringify(event.tool_results) : null,
          })
          syncMessagesIfCurrent(currentSession.id)
          void syncSessions()
          return

        case 'error':
          hasTerminalEvent = true
          messagesStore.finalizeStreamingError({
            id: event.message_id,
            created_at: event.created_at,
            content: event.message,
          })
          syncMessagesIfCurrent(currentSession.id)
          void syncSessions()
          return

        case 'interrupt':
          hasTerminalEvent = true
          messagesStore.setStreamingInterrupt(event.questions)
          syncMessagesIfCurrent(currentSession.id)
          void syncSessions()
          return
      }

      assertNever(event)
    }

    try {
      await sendChatResumeStream(
        {
          session_id: currentSession.id,
          answers
        },
        handleEvent,
        { signal: controller.signal }
      )

      if (!hasTerminalEvent) {
        throw new Error('流式响应未正常结束')
      }
    } catch (error) {
      if (isAbortError(error)) {
        console.info('恢复流式请求已取消')
        messagesStore.finalizeStreamingInterrupted()
        void syncSessions()
        return
      }

      console.error('[diagnose] 恢复流式异常:', (error as Error)?.constructor?.name, (error as Error)?.message)
      console.error('恢复发送消息失败:', error)
      messagesStore.clearStreamingMessage()
      syncMessagesIfCurrent(currentSession.id)
      void syncSessions()
      throw error
    } finally {
      if (activeStreamController.value === controller) {
        activeStreamController.value = null
      }
      isSending.value = false
    }
  }

  return {
    isSending,
    streamMode,
    enableThinking, // 新增导出
    contextWarning,
    sendMessage,
    resumeMessage,
    stopStreaming
  }
}
