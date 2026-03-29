// 会话类型
export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number  // 消息总数 - 2025-01-01
  messages?: Message[]
}

export interface SessionCreate {
  title?: string
}

export interface SessionUpdate {
  title?: string
}

// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  session_id: string
  created_at: string
  tool_calls?: string | null
  tool_results?: string | null
}

export interface MessageCreate {
  role: Message['role']
  content: string
  session_id: string
  tool_calls?: string | null
  tool_results?: string | null
}

export type StreamStage = 'thinking' | 'retrieving' | 'querying' | 'writing'

export interface StreamToolCall {
  id: string
  name: string
  args?: Record<string, unknown> | unknown[] | string
  args_text?: string
  status?: 'started' | 'streaming' | 'completed'
}

export interface StreamToolResult {
  id: string
  content: string
}

export type StreamEvent =
  | {
      type: 'token'
      text: string
      node?: string
    }
  | {
      type: 'status'
      stage: StreamStage
      text: string
      source?: string
      detail?: Record<string, unknown>
    }
  | {
      type: 'tool_call'
      id: string
      name: string
      args_text?: string
      status: 'started' | 'streaming' | 'completed'
    }
  | {
      type: 'tool_result'
      id: string
      content: string
    }
  | {
      type: 'final'
      content: string
      tool_calls?: StreamToolCall[] | null
      tool_results?: Record<string, string> | null
      message_id?: string
      created_at?: string
    }
  | {
      type: 'error'
      message: string
      retryable?: boolean
      message_id?: string
      created_at?: string
    }
  | {
      type: string
      [key: string]: unknown
    }

export interface FinalizedStreamingMessage {
  id?: string
  created_at?: string
  content?: string
  tool_calls?: string | null
  tool_results?: string | null
}

// 流式消息状态（临时显示）- 2025-01-01
export interface StreamingMessage {
  id: string
  session_id: string
  role: 'assistant'
  content: string
  created_at: string
  isStreaming: boolean
  statusText: string | null
  stage: StreamStage | null
  toolCalls: StreamToolCall[]
  toolResults: Record<string, string>
  error: string | null
}

// 聊天请求类型 - 2025-01-01
export interface ChatRequest {
  message: string
  session_id: string
  stream: boolean
}

// 聊天响应类型 - 2025-01-01
export interface ChatResponse {
  session_id: string
  message: Message
  is_complete: boolean
}
