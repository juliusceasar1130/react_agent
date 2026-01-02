// 流式聊天逻辑封装
// 创建日期: 2025-01-01

import { ref } from 'vue'
import { sendChatStream, sendChatMessage } from '@/api/chat'
import { useMessagesStore } from '@/stores/messages'
import { useSessionsStore } from '@/stores/sessions'
import type { Message } from '@/types'  // 新增 - 2025-01-01

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
    // 开始流式消息（创建临时消息对象）
    messagesStore.startStreamingMessage(sessionId)

    // 调用流式 API
    await sendChatStream(
      { message: content, session_id: sessionId, stream: true },
      // onChunk - 逐字追加内容
      (chunk) => {
        if (!chunk.is_final && chunk.content) {
          messagesStore.appendStreamingContent(chunk.content)
        }
      },
      // onError
      (error) => {
        console.error('流式错误:', error)
        messagesStore.clearStreamingMessage()
        throw error
      },
      // onComplete - 流式结束后清除临时状态并重新加载消息列表 - 2025-01-01
      async () => {
        messagesStore.clearStreamingMessage()
        await messagesStore.fetchMessages(sessionId)
        // 更新消息数量（user + assistant = 2条）- 2025-01-01
        sessionsStore.incrementMessageCount(sessionId, 2)
      }
    )
  }

  /**
   * 处理非流式消息
   */
  const handleNormalMessage = async (sessionId: string, content: string) => {
    const response = await sendChatMessage({
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
