# RAG 检索业务知识结构化呈现与前端 UI 折叠卡片实现计划 (阶段二)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RAG 检索的业务资料在**大模型生成文本前提前流式抛出**展示给前端，消除等待焦虑；并在前端聊天气泡底部提供高质感的可折叠“参考业务术语”卡片，不污染数据库。

**Architecture:**
1. 后端：在 `app/schemas.py` 中增加 `RAGContextStreamEvent` 结构，表示流式前置 RAG 事件。
2. 后端：在 `app/services.py` 的 `_stream_execution_loop` 循环开头，在 `astream` 启动后的最早期（首个 token 前），异步查取 `aget_state` 图状态。若命中 RAG 缓存，立刻 `_emit` 流式自定义 `rag_context` 事件。
3. 后端：在 `app/api.py` 的两处流式 API（`chat_session_stream` 与 `resume_session_stream`）中，对收到的 `rag_context` 事件直接进行透传编码并 `yield _encode_sse(event)` 发给前端。
4. 前端：在 `types/index.ts` 的 `StreamEvent`、`Message` 和 `StreamingMessage` 中扩展 `rag_context` 结构支持。
5. 前端：在 `api/chat.ts` 中解析流式响应的 `rag_context` 类型并回传；在 `composables/useChatStream.ts` 中将提前收到的 RAG 数据绑定给临时 `streamingMessage` 实例；在 `stores/messages.ts` 中，在流式完成（`completeStreamingMessage`）时将其过渡转移给正式 Message。
6. 前端：修改 `MessageItem.vue`，实现底部细节折叠卡片组件的优雅渲染。

**Tech Stack:** FastAPI, LangGraph, Vue 3, Tailwind CSS, Python Pytest.

---

### Task 1: 后端 SSE 协议扩展与 services/api 提前抛出实现

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services.py`
- Modify: `backend/app/api.py`
- Test: `backend/app/test_services_stream_filtering.py`

- [ ] **Step 1: 在 schemas.py 中定义 RAGContextStreamEvent 结构**

修改 [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py)，新增 `RAGContextStreamEvent` 流式结构：

```python
class RAGContextPayload(BaseModel):
    title: str
    domain: str
    aliases: List[str]
    content: str


class RAGContextStreamEvent(BaseModel):
    type: Literal["rag_context"]
    rag_context: List[RAGContextPayload]
```

- [ ] **Step 2: 在 services.py 执行流中提取并提前 _emit 数据源事件**

修改 [services.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/services.py)，在 `_produce_events` 循环（大约 673 行 `async for chunk in source_iter:` 处）的最开头，增加异步轮询提取 RAG 状态的逻辑，提取成功后立即发送：

```python
                has_sent_rag = False
                async for chunk in source_iter:
                    if not chunk:
                        continue

                    # 🚀 在流式早期，如检测到状态中 RAG 已就绪且未发送，提前触发自定义 RAG 事件发送给客户端
                    if not has_sent_rag:
                        try:
                            state = await self.agent.aget_state(resolved_config)
                            rag_context_list = state.values.get("rag_context", []) if state else []
                            rag_query = state.values.get("rag_query", "") if state else ""
                            if isinstance(rag_query, str):
                                rag_query = rag_query.strip()

                            # 只有当 RAG 检索到的提问词 rag_query 与本轮实际用户提问 user_query 匹配时，才证明最新数据已写入 Checkpoint 并可被提前发出
                            if rag_context_list and (user_query is None or rag_query == user_query):
                                rag_context_payload = [
                                    {
                                        "title": doc.metadata.get("term") or doc.metadata.get("title") or "未命名术语",
                                        "domain": doc.metadata.get("domain", "通用"),
                                        "aliases": doc.metadata.get("aliases", []),
                                        "content": doc.page_content,
                                    }
                                    for doc in rag_context_list
                                ]
                                await _emit({
                                    "type": "rag_context",
                                    "rag_context": rag_context_payload
                                })
                                has_sent_rag = True
                        except Exception as e:
                            logger.warning("流式执行中提前提取并发送 RAG 状态失败: %s", e)
                            has_sent_rag = True  # 真实报错异常时才设为 True 避免产生崩溃死循环
```

对 `process_stream_resume` 中的 `_produce_events` 做同样的逻辑植入。

- [ ] **Step 3: 在 api.py 的两个流式接口中直接透传 rag_context 事件**

修改 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py)：
1. 在 `chat_session_stream`（在 610 行附近）增加对 `rag_context` 事件的拦截透传：
```python
                if event_type == "rag_context":
                    yield _encode_sse(event)
                    continue
```
2. 在 `resume_session_stream`（在 920 行附近）增加相同的拦截透传逻辑。

- [ ] **Step 4: 运行后端测试验证系统运行无故障**

在终端运行：
`pytest backend/app/test_services_stream_filtering.py -v`

---

### Task 2: 前端 TypeScript 类型定义升级

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 修改 Message、StreamEvent 与 StreamingMessage 接口**

修改 [types/index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts)：
1. 在 `Message` 接口增加可选的临时字段：
```typescript
  rag_context?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
```
2. 在 `StreamEvent` 中扩展 `rag_context` 结构定义：
```typescript
  | {
      type: 'rag_context'
      rag_context: Array<{
        title: string
        domain: string
        aliases: string[]
        content: string
      }>
    }
```
3. 在 `StreamingMessage` 接口中增加 `ragContext` 缓存字段：
```typescript
  ragContext?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
```

---

### Task 3: 前端 API 解析与状态过渡缓存机制开发

**Files:**
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/composables/useChatStream.ts`
- Modify: `frontend/src/stores/messages.ts`

- [ ] **Step 1: 升级前端 API 消息流解析模块**

修改 [frontend/src/api/chat.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/api/chat.ts)，在解析 SSE 事件时（如约 150 行及 300 行附近），拦截 `type === 'rag_context'`：
```typescript
      case 'rag_context':
        return {
          type: 'rag_context',
          rag_context: data.rag_context,
        }
```

- [ ] **Step 2: 修改 Messages Store 完成态转换函数**

修改 [frontend/src/stores/messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts)：
1. 在 `FinalizedStreamingMessage` 接口追加 `rag_context`：
```typescript
export interface FinalizedStreamingMessage {
  // ... 其他
  rag_context?: Array<{
    title: string
    domain: string
    aliases: string[]
    content: string
  }> | null
}
```
2. 修改 `completeStreamingMessage` 函数，将流式缓存的 `ragContext` 透传给正式 `finalizedMessage.rag_context`：
```typescript
  const completeStreamingMessage = (payload: FinalizedStreamingMessage = {}) => {
    if (!streamingMessage.value) return null

    const finalizedMessage: Message = {
      id: payload.id ?? streamingMessage.value.id,
      session_id: streamingMessage.value.session_id,
      role: 'assistant',
      content: payload.content ?? streamingMessage.value.content,
      created_at: payload.created_at ?? streamingMessage.value.created_at,
      tool_calls: payload.tool_calls ?? (
        streamingMessage.value.toolCalls.length
          ? JSON.stringify(streamingMessage.value.toolCalls)
          : null
      ),
      tool_results: payload.tool_results ?? (
        Object.keys(streamingMessage.value.toolResults).length
          ? JSON.stringify(streamingMessage.value.toolResults)
          : null
      ),
      // 🆕 临时透传，用于活跃会话在流式结束后的卡片展现
      rag_context: payload.rag_context ?? streamingMessage.value.ragContext
    }

    messages.value.push(finalizedMessage)
    streamingMessage.value = null
    isStreaming.value = false
    return finalizedMessage
  }
```

- [ ] **Step 3: 修改 useChatStream Composable 状态绑定**

修改 [useChatStream.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/composables/useChatStream.ts)，在处理事件的分支（有两处）中，收到 `rag_context` 时将其写入 `streamingMessage` 中：
```typescript
        case 'rag_context':
          if (messagesStore.streamingMessage) {
            messagesStore.streamingMessage.ragContext = parsed.rag_context
          }
          break
```

---

### Task 4: 聊天气泡底部 RAG 结构化卡片渲染与组件开发

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: 修改 MessageItem.vue 追加 RAG 折叠面板组件**

修改 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue)：
1. 编写 `parsedRagContext` 计算属性，兼容处理流式状态与完成状态的数据源读取：
```typescript
const parsedRagContext = computed(() => {
  if (streamingState.value?.ragContext) {
    return streamingState.value.ragContext
  }
  return (props.message as Message).rag_context ?? []
})
```
2. 在模板中的内容渲染下方，插入精美的 `<details>` 折叠面板组件。该面板具备扁平化无衬线背景和渐显动画：
```html
        <!-- 第二阶段新增：参考业务术语折叠卡片 -->
        <div v-if="!isUser && parsedRagContext.length > 0" class="mt-4 px-1.5 animate-fade-in">
          <details class="group rounded-[20px] border border-neutral-200/80 bg-neutral-50/50 p-3.5 text-xs text-neutral-600 transition-all duration-200">
            <summary class="flex cursor-pointer select-none items-center justify-between font-medium text-neutral-700 hover:text-primary list-none">
              <span class="flex items-center gap-2">
                <svg class="h-4 w-4 text-neutral-500 group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <span class="text-xs font-semibold text-neutral-800">参考业务术语 ({{ parsedRagContext.length }} 条)</span>
              </span>
              <svg class="h-3.5 w-3.5 text-neutral-400 transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <div class="mt-3 space-y-4 border-t border-neutral-200/60 pt-3">
              <div v-for="item in parsedRagContext" :key="item.title" class="space-y-1.5 text-left">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-[6px] bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                    {{ item.domain }}
                  </span>
                  <span class="font-bold text-neutral-800 text-[12px]">{{ item.title }}</span>
                  <span v-if="item.aliases && item.aliases.length" class="text-[10px] text-neutral-400 font-medium">
                    (别名: {{ item.aliases.join(', ') }})
                  </span>
                </div>
                <p class="pl-0.5 text-[11px] leading-5 text-neutral-500 whitespace-pre-line font-medium">
                  {{ item.content }}
                </p>
              </div>
            </div>
          </details>
        </div>
```

- [ ] **Step 2: 运行前端打包构建检测**

在前端执行：
`npm run build:check`

Expected Output:
`✓ built in ...s` (100% 编译成功)

---

### Task 5: 联调验证与提交记录

- [ ] **Step 1: 手动浏览器发送提问，联调确认：**
  1. AI 刚刚发问后 1 秒内（文本生成之前），折叠卡片 `参考业务术语 (N 条)` 即时显现。
  2. 点击该折叠卡片能够展开，完美渲染业务域、别名和内容，没有宋体锯齿。
  3. AI 气泡同步流式打字生成思考过程与表格，排版完美。
  4. 回答完成后刷新页面，该术语参考卡片因不落库自动隐藏，保持历史消息纯净。

- [ ] **Step 2: 更新变更记录**

在 `changelog.md` 中记录本次阶段二的交付情况。
