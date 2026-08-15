export interface QuestionOption {
  label: string
  description?: string
}

export interface QuestionItem {
  question: string
  header?: string
  multiSelect: boolean
  options?: QuestionOption[]
}

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

export interface LexiconContext {
  tables: Array<{ table_name: string; ddl: string }>
  values: Array<{ table_name: string; column_name: string; exact_value: string }>
  rows: Array<{ table_name: string; primary_key_column: string; primary_key_val: string; row_content: string }>
}

// 工具产物类型（SQL 查询结果 / 图表 / 文件导出）
export interface ToolArtifact {
  kind: string
  columns?: string[]
  rows?: any[]
  row_count?: number
  truncated?: boolean
  query_time?: string
  source_tables?: string[]
  [key: string]: unknown
}

export interface SubagentSessionState {
  id: string // task call_id
  name: string // e.g. "sql_domain_agent"
  title?: string // human readable display name e.g. "SQL数据助手"
  description?: string
  status: 'running' | 'completed' | 'error' | 'interrupted'
  reasoningText: string
  reasoningStartTime?: number
  reasoningEndTime?: number
  reasoningDuration?: number
  toolCalls: StreamToolCall[]
  toolResults: Record<string, string>
  content: string
  error?: string
}

// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  reasoningText?: string
  reasoningDuration?: number
  session_id: string
  created_at: string
  tool_calls?: string | null
  tool_results?: string | null
  is_interrupted?: boolean
  questions?: QuestionItem[]
  feedback?: 'none' | 'like' | 'dislike' | 'collected' | 'approved'
  refined_payload?: string | null  // LLM 预提纯草稿 JSON 字符串
  rag_context?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
  lexicon_context?: LexiconContext | null
  tool_artifact?: ToolArtifact | null
  active_subagent?: string | null
  subagent_display_name?: string | null
  subagents?: Record<string, SubagentSessionState>
}

export interface MessageCreate {
  role: Message['role']
  content: string
  session_id: string
  tool_calls?: string | null
  tool_results?: string | null
}

export interface ContextWarningPayload {
  estimated_input_tokens: number
  warn_tokens: number
  context_window: number
  output_reserve: number
  safety_buffer: number
  message_count: number
  tool_count: number
  recommended_action: 'start_new_session'
  source: 'context_warning'
}

export interface ExportArtifact {
  kind: 'file_export'
  file_id: string
  filename: string
  media_type?: string
  size_bytes?: number
  row_count?: number
  col_count?: number
  columns?: string[]
  created_at?: string
  expires_at?: string
  message?: string
}

export interface ChartArtifactRef {
  kind: 'chart_artifact_ref'
  chart_id: string
  chart_type: 'line' | 'bar'
  title: string
  point_count: number
  created_at?: string
  expires_at?: string
  message?: string
}

export interface ChartArtifactSeries {
  name: string
  field: string
  y_axis: 'left' | 'right'
  category_field?: string
  category_value?: string
  color?: string
}

export interface ChartArtifact {
  kind: 'chart_spec'
  chart_id: string
  chart_type: 'line' | 'bar'
  title: string
  description?: string
  x_field: string
  series: ChartArtifactSeries[]
  rows: Array<Record<string, string | number | null>>
  created_at?: string
  expires_at?: string
}

export type StreamStage = 'thinking' | 'retrieving' | 'querying' | 'writing'

export interface StreamToolCall {
  id: string
  name: string
  args?: Record<string, unknown> | unknown[] | string
  args_text?: string
  status?: StreamToolCallStatus
  subagent_id?: string
  subagent_name?: string
}

export type StreamToolCallStatus = 'started' | 'streaming' | 'completed'

export type StreamEvent =
  | {
      type: 'token'
      text: string
      node?: string
      subagent_id?: string
      subagent_name?: string
    }
  | {
      type: 'reasoning'
      text: string
      node?: string
      subagent_id?: string
      subagent_name?: string
    }
  | {
      type: 'status'
      stage: StreamStage
      text: string
      source?: string
      detail?: Record<string, unknown>
      subagent_id?: string
      subagent_name?: string
    }
  | {
      type: 'tool_call'
      id: string
      name: string
      args_text?: string
      status: StreamToolCallStatus
      subagent_id?: string
      subagent_name?: string
    }
  | {
      type: 'tool_result'
      id: string
      content: string
      subagent_id?: string
      subagent_name?: string
    }
  | {
      type: 'final'
      content: string
      tool_calls?: StreamToolCall[] | null
      tool_results?: Record<string, string> | null
      subagents?: Record<string, SubagentSessionState> | null
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
      type: 'interrupt'
      questions: QuestionItem[]
      session_id: string
    }
  | {
      type: 'rag_context'
      rag_context: Array<{
        title: string
        domain: string
        aliases: string[]
        content: string
      }>
    }
  | {
      type: 'lexicon_context'
      lexicon_context: LexiconContext
    }
  | {
      type: 'tool_artifact'
      artifact: ToolArtifact
    }
  | {
      type: 'subagent_change'
      active_subagent: string
      display_name: string
    }
  | {
      type: 'plan_update'
      plan: Record<string, unknown>
    }

export interface FinalizedStreamingMessage {
  id?: string
  created_at?: string
  content?: string
  tool_calls?: string | null
  tool_results?: string | null
  rag_context?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
  lexicon_context?: LexiconContext | null
  tool_artifact?: Message['tool_artifact']
  subagents?: Record<string, SubagentSessionState>
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
  reasoningText?: string
  reasoningDuration?: number
  requestStartTime?: number | null
  reasoningStartTime?: number | null
  reasoningEndTime?: number | null
  thinkingEnded?: boolean
  needsReasoningSeparator?: boolean
  error: string | null
  isInterrupted?: boolean
  questions?: QuestionItem[]
  feedback?: 'none' | 'like' | 'dislike' | 'collected' | 'approved'
  ragContext?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
  lexiconContext?: LexiconContext | null
  tool_artifact?: ToolArtifact | null
  active_subagent?: string | null
  subagent_display_name?: string | null
  subagents?: Record<string, SubagentSessionState>
}

// 聊天请求类型 - 2025-01-01
export interface ChatRequest {
  message: string
  session_id: string
  stream: boolean
  enable_thinking?: boolean // 新增：是否启用思考模式
}

// 聊天响应类型 - 2025-01-01
export interface ChatResponse {
  session_id: string
  message: Message
  is_complete: boolean
  context_warning?: ContextWarningPayload | null
}
