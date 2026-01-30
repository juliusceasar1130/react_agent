// 聊天 API - 流式和非流式消息发送
// 创建日期: 2025-01-01

import axios from 'axios'
import type { ChatRequest, ChatResponse, StreamChunk } from '@/types'

const API_BASE = '/rearch/api/chat'  // 使用相对路径，适配 Nginx 代理

/**
 * 非流式消息发送
 * @param data 聊天请求
 * @returns 聊天响应
 */
export const sendChatMessage = async (data: ChatRequest): Promise<ChatResponse> => {
  const response = await axios.post(`${API_BASE}/message`, data)
  return response.data
}

/**
 * 流式消息发送（SSE 流处理）
 * @param data 聊天请求
 * @param onChunk 接收到内容块时的回调
 * @param onError 发生错误时的回调
 * @param onComplete 完成时的回调
 */
export const sendChatStream = async (
  data: ChatRequest,
  onChunk: (chunk: StreamChunk) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> => {
  const response = await fetch(`${API_BASE}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('Response body is null')
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onComplete()
            return
          }

          try {
            const parsed = JSON.parse(data) as StreamChunk
            onChunk(parsed)
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }
    }
  } catch (error) {
    onError(error as Error)
  }
}
