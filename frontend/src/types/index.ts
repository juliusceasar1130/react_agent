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
}

export interface MessageCreate {
  role: Message['role']
  content: string
  session_id: string
}

// 流式响应块类型 - 2025-01-01
export interface StreamChunk {
  content: string
  is_final: boolean
  tool_calls: any[] | null
}

// 流式消息状态（临时显示）- 2025-01-01
export interface StreamingMessage {
  id: string
  session_id: string
  role: 'assistant'
  content: string
  isStreaming: true
  timestamp: Date
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
