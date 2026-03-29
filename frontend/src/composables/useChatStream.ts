// 流式聊天逻辑封装
// 创建日期: 2025-01-01
// 修改时间: 2026-03-27 17:42 Asia/Shanghai
// 主要修改内容:
// - 改为结构化 StreamEvent 驱动
// - 实现本地完成落定 + 后台静默同步
// - 2026-03-27 22:12 Asia/Shanghai: 错误场景直接落定为最终消息，避免残留过程态

import { ref } from 'vue'
import { sendChatStream, sendChatMessage } from '@/api/chat'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import type { Message, StreamEvent, StreamToolCall } from '@/types'

/**
 * 流式聊天 Composable
 * 封装流式和非流式消息发送逻辑
 */
export function useChatStream() {
  const messagesStore = useMessagesStore()
  const sessionsStore = useSessionsStore()

  const isSending = ref(false)
  const streamMode = ref(false)  // 流式模式开关状态

  /**
   * 发送消息（根据 streamMode 选择流式或非流式）
   */
  const sendMessage = async (content: string) => {
    const currentSession = sessionsStore.currentSession
    if (!currentSession) {
      throw new Error('没有选择会话')
    }

    isSending.value = true

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
      console.error('发送消息失败:', error)
      // 发送失败时移除临时用户消息 - 2025-01-01
      const index = messagesStore.messages.findIndex(m => m.id === tempUserMessage.id)
      if (index !== -1) {
        messagesStore.messages.splice(index, 1)
      }
      messagesStore.clearStreamingMessage()
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

        case 'final':
          hasTerminalEvent = true
          messagesStore.completeStreamingMessage({
            id: event.message_id,
            created_at: event.created_at,
            content: event.content,
            tool_calls: event.tool_calls ? JSON.stringify(event.tool_calls) : null,
            tool_results: event.tool_results ? JSON.stringify(event.tool_results) : null,
          })
          sessionsStore.incrementMessageCount(sessionId, 2)
          void messagesStore.fetchMessages(sessionId).catch((error) => {
            console.error('静默同步消息失败:', error)
          })
          return

        case 'error':
          hasTerminalEvent = true
          messagesStore.finalizeStreamingError({
            id: event.message_id,
            created_at: event.created_at,
            content: event.message,
          })
          sessionsStore.incrementMessageCount(sessionId, 2)
          void messagesStore.fetchMessages(sessionId).catch((error) => {
            console.error('错误后的消息同步失败:', error)
          })
          return

        default:
          return
      }
    }

    await sendChatStream(
      { message: content, session_id: sessionId, stream: true },
      handleEvent
    )

    if (!hasTerminalEvent) {
      throw new Error('流式响应未正常结束')
    }
  }

  /**
   * 处理非流式消息
   */
  const handleNormalMessage = async (sessionId: string, content: string) => {
    await sendChatMessage({
      message: content,
      session_id: sessionId,
      stream: false
    })

    // 非流式完成后，重新加载消息列表
    await messagesStore.fetchMessages(sessionId)
    // 更新消息数量（user + assistant = 2条）- 2025-01-01
    sessionsStore.incrementMessageCount(sessionId, 2)
  }

  return {
    isSending,
    streamMode,
    sendMessage
  }
}
