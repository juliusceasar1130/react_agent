// 聊天 API - 流式和非流式消息发送
// 创建日期: 2025-01-01
// 修改时间: 2026-03-27 17:38 Asia/Shanghai
// 主要修改内容:
// - 重写 SSE 解析器，支持跨 chunk buffer 累积
// - 将流式回调从旧版 chunk 模式升级为结构化 StreamEvent

import axios from 'axios'
import type { ChatRequest, ChatResponse, StreamEvent } from '@/types'

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

const extractSseEvents = (buffer: string): { events: string[]; rest: string } => {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')

  if (parts.length === 1) {
    return { events: [], rest: normalized }
  }

  return {
    events: parts.slice(0, -1),
    rest: parts[parts.length - 1] ?? ''
  }
}

const parseSsePayload = (rawEvent: string): string | null => {
  const dataLines = rawEvent
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())

  if (!dataLines.length) {
    return null
  }

  return dataLines.join('\n')
}

/**
 * 流式消息发送（SSE 流处理）
 * @param data 聊天请求
 * @param onEvent 接收到事件时的回调
 */
export const sendChatStream = async (
  data: ChatRequest,
  onEvent: (event: StreamEvent) => void
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

  let buffer = ''
  let sawTerminalEvent = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = extractSseEvents(buffer)
      buffer = rest

      for (const rawEvent of events) {
        const payload = parseSsePayload(rawEvent)
        if (!payload) continue

        if (payload === '[DONE]') {
          if (!sawTerminalEvent) {
            throw new Error('流式响应在收到终止标记前未返回 final 或 error 事件')
          }
          return
        }

        try {
          const parsed = JSON.parse(payload) as StreamEvent
          if (parsed.type === 'final' || parsed.type === 'error') {
            sawTerminalEvent = true
          }
          onEvent(parsed)
        } catch (error) {
          console.error('Parse error:', error, payload)
        }
      }
    }

    const trailingPayload = parseSsePayload(buffer)
    if (trailingPayload && trailingPayload !== '[DONE]') {
      const parsed = JSON.parse(trailingPayload) as StreamEvent
      if (parsed.type === 'final' || parsed.type === 'error') {
        sawTerminalEvent = true
      }
      onEvent(parsed)
    }

    if (!sawTerminalEvent) {
      throw new Error('流式连接已结束，但未收到 final 或 error 事件')
    }
  } finally {
    reader.releaseLock()
  }
}
