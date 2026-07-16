// 聊天 API - 流式和非流式消息发送
// 创建日期: 2025-01-01
// 修改时间: 2026-03-31 21:31 Asia/Shanghai
// 主要修改内容:
// - 重写 SSE 解析器，支持跨 chunk buffer 累积
// - 将流式回调从旧版 chunk 模式升级为结构化 StreamEvent
// - 2026-03-29 23:10 Asia/Shanghai: 支持通过 AbortSignal 取消流式请求
// - 2026-03-31 21:31 Asia/Shanghai: 新增事件 schema 运行时校验，拒绝未知流式事件

import axios from 'axios'
import type {
  ChatRequest,
  ChatResponse,
  StreamEvent,
  StreamStage,
  StreamToolCall,
  StreamToolCallStatus,
  QuestionItem,
} from '@/types'

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

const STREAM_EVENT_TYPES = new Set<StreamEvent['type']>([
  'token',
  'status',
  'tool_call',
  'tool_result',
  'final',
  'error',
  'interrupt',
  'rag_context',
  'lexicon_context'
])

const STREAM_STAGES = new Set<StreamStage>(['thinking', 'retrieving', 'querying', 'writing'])
const TOOL_CALL_STATUSES = new Set<StreamToolCallStatus>(['started', 'streaming', 'completed'])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isOptionalString = (value: unknown): value is string | undefined =>
  value === undefined || typeof value === 'string'

const isStringRecord = (value: unknown): value is Record<string, string> => {
  if (!isRecord(value)) {
    return false
  }

  return Object.values(value).every((item) => typeof item === 'string')
}

const isStreamStage = (value: unknown): value is StreamStage =>
  typeof value === 'string' && STREAM_STAGES.has(value as StreamStage)

const isToolCallStatus = (value: unknown): value is StreamToolCallStatus =>
  typeof value === 'string' && TOOL_CALL_STATUSES.has(value as StreamToolCallStatus)

const parseStreamEvent = (payload: string): StreamEvent | null => {
  const parsed: unknown = JSON.parse(payload)
  if (!isRecord(parsed) || typeof parsed.type !== 'string' || !STREAM_EVENT_TYPES.has(parsed.type as StreamEvent['type'])) {
    return null
  }

  switch (parsed.type) {
    case 'token':
      if (typeof parsed.text !== 'string' || !isOptionalString(parsed.node)) {
        return null
      }
      return {
        type: 'token',
        text: parsed.text,
        node: parsed.node,
      }

    case 'status':
      if (
        typeof parsed.text !== 'string'
        || !isStreamStage(parsed.stage)
        || !isOptionalString(parsed.source)
        || (parsed.detail !== undefined && !isRecord(parsed.detail))
      ) {
        return null
      }
      return {
        type: 'status',
        stage: parsed.stage,
        text: parsed.text,
        source: parsed.source,
        detail: parsed.detail,
      }

    case 'tool_call':
      if (
        typeof parsed.id !== 'string'
        || typeof parsed.name !== 'string'
        || !isOptionalString(parsed.args_text)
        || !isToolCallStatus(parsed.status)
      ) {
        return null
      }
      return {
        type: 'tool_call',
        id: parsed.id,
        name: parsed.name,
        args_text: parsed.args_text,
        status: parsed.status,
      }

    case 'tool_result':
      if (typeof parsed.id !== 'string' || typeof parsed.content !== 'string') {
        return null
      }
      return {
        type: 'tool_result',
        id: parsed.id,
        content: parsed.content,
      }

    case 'rag_context':
      if (!Array.isArray(parsed.rag_context)) {
        return null
      }
      return {
        type: 'rag_context',
        rag_context: parsed.rag_context,
      }

    case 'lexicon_context':
      if (!isRecord(parsed.lexicon_context)) {
        return null
      }
      return {
        type: 'lexicon_context',
        lexicon_context: parsed.lexicon_context as any,
      }

    case 'final':
      if (
        typeof parsed.content !== 'string'
        || !isOptionalString(parsed.message_id)
        || !isOptionalString(parsed.created_at)
        || (parsed.tool_results !== undefined && parsed.tool_results !== null && !isStringRecord(parsed.tool_results))
        || (
          parsed.tool_calls !== undefined
          && parsed.tool_calls !== null
          && (
            !Array.isArray(parsed.tool_calls)
            || parsed.tool_calls.some((item) =>
              !isRecord(item)
              || typeof item.id !== 'string'
              || typeof item.name !== 'string'
              || !isToolCallStatus(item.status)
              || (item.args_text !== undefined && typeof item.args_text !== 'string')
            )
          )
        )
      ) {
        return null
      }
      return {
        type: 'final',
        content: parsed.content,
        tool_calls: parsed.tool_calls as StreamToolCall[] | null | undefined,
        tool_results: parsed.tool_results as Record<string, string> | null | undefined,
        message_id: parsed.message_id,
        created_at: parsed.created_at,
      }

    case 'error':
      if (
        typeof parsed.message !== 'string'
        || (parsed.retryable !== undefined && typeof parsed.retryable !== 'boolean')
        || !isOptionalString(parsed.message_id)
        || !isOptionalString(parsed.created_at)
      ) {
        return null
      }
      return {
        type: 'error',
        message: parsed.message,
        retryable: parsed.retryable,
        message_id: parsed.message_id,
        created_at: parsed.created_at,
      }

    case 'interrupt':
      if (
        !parsed.questions
        || !Array.isArray(parsed.questions)
        || typeof parsed.session_id !== 'string'
        || parsed.questions.some((q) =>
          !isRecord(q)
          || typeof q.question !== 'string'
          || (
            q.options !== undefined
            && q.options !== null
            && (
              !Array.isArray(q.options)
              || q.options.some((o) =>
                !isRecord(o)
                || typeof o.label !== 'string'
                || (o.description !== undefined && typeof o.description !== 'string')
                || (o.preview !== undefined && typeof o.preview !== 'string')
              )
            )
          )
        )
      ) {
        return null
      }
      return {
        type: 'interrupt',
        questions: parsed.questions as QuestionItem[],
        session_id: parsed.session_id,
      }
  }

  return null
}

/**
 * 流式消息发送（SSE 流处理）
 * @param data 聊天请求
 * @param onEvent 接收到事件时的回调
 */
export const sendChatStream = async (
  data: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  options: {
    signal?: AbortSignal
  } = {}
): Promise<void> => {
  const response = await fetch(`${API_BASE}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: options.signal
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
      if (done) {
        console.debug('[sendChatStream] read done, buffer尾长:', buffer.length, 'sawTerminalEvent:', sawTerminalEvent)
        break
      }

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
          console.debug('[sendChatStream] 收到 [DONE], 正常结束, sawTerminalEvent:', sawTerminalEvent)
          return
        }

        try {
          const parsed = parseStreamEvent(payload)
          if (!parsed) {
            console.warn('忽略不符合协议的流式事件:', payload)
            continue
          }
          if (parsed.type === 'final' || parsed.type === 'error' || parsed.type === 'interrupt') {
            sawTerminalEvent = true
            console.debug('[sendChatStream] 收到终端事件:', parsed.type)
          }
          onEvent(parsed)
        } catch (error) {
          console.error('Parse error:', error, payload)
        }
      }
    }

    const trailingPayload = parseSsePayload(buffer)
    if (trailingPayload && trailingPayload !== '[DONE]') {
      const parsed = parseStreamEvent(trailingPayload)
      if (!parsed) {
        console.debug('[sendChatStream] 尾部非标准payload, buffer:', buffer)
        throw new Error('流式连接尾部包含不符合协议的事件')
      }
      if (parsed.type === 'final' || parsed.type === 'error' || parsed.type === 'interrupt') {
        sawTerminalEvent = true
      }
      onEvent(parsed)
    }

    if (!sawTerminalEvent) {
      console.error('[sendChatStream] 流结束但无终端事件, buffer:', buffer)
      throw new Error('流式连接已结束，但未收到 final、error 或 interrupt 事件')
    }
  } finally {
    reader.releaseLock()
  }
}

/**
 * 恢复挂起的流式消息发送（SSE 流处理）
 * @param data 恢复请求
 * @param onEvent 接收到事件时的回调
 */
export const sendChatResumeStream = async (
  data: { session_id: string; answers: Record<string, string | string[]> },
  onEvent: (event: StreamEvent) => void,
  options: {
    signal?: AbortSignal
  } = {}
): Promise<void> => {
  const response = await fetch(`${API_BASE}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    signal: options.signal
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
      if (done) {
        console.debug('[sendChatResume] read done, buffer尾长:', buffer.length, 'sawTerminalEvent:', sawTerminalEvent)
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = extractSseEvents(buffer)
      buffer = rest

      for (const rawEvent of events) {
        const payload = parseSsePayload(rawEvent)
        if (!payload) continue

        if (payload === '[DONE]') {
          if (!sawTerminalEvent) {
            console.error('[sendChatResume] 收到 [DONE] 但无终端事件, buffer:', buffer)
            throw new Error('流式响应在收到终止标记前未返回 final、error 或 interrupt 事件')
          }
          console.debug('[sendChatResume] 收到 [DONE], 正常结束')
          return
        }

        try {
          const parsed = parseStreamEvent(payload)
          if (!parsed) {
            console.warn('[sendChatResume] 忽略不符合协议的流式事件:', payload)
            continue
          }
          if (parsed.type === 'final' || parsed.type === 'error' || parsed.type === 'interrupt') {
            sawTerminalEvent = true
            console.debug('[sendChatResume] 收到终端事件:', parsed.type)
          }
          onEvent(parsed)
        } catch (error) {
          console.error('Parse error:', error, payload)
        }
      }
    }

    const trailingPayload = parseSsePayload(buffer)
    if (trailingPayload && trailingPayload !== '[DONE]') {
      const parsed = parseStreamEvent(trailingPayload)
      if (!parsed) {
        console.debug('[sendChatResume] 尾部非标准payload, buffer:', buffer)
        throw new Error('流式连接尾部包含不符合协议的事件')
      }
      if (parsed.type === 'final' || parsed.type === 'error' || parsed.type === 'interrupt') {
        sawTerminalEvent = true
      }
      onEvent(parsed)
    }

    if (!sawTerminalEvent) {
      console.error('[sendChatResume] 流结束但无终端事件, buffer:', buffer)
      throw new Error('流式连接已结束，但未收到 final、error 或 interrupt 事件')
    }
  } finally {
    reader.releaseLock()
  }
}
