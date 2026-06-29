# 反馈收集基础建设与落库 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现用户点击消息卡片底部的“赞/踩/收藏”反馈，并将该状态持久化记录到 PostgreSQL 数据库 `chat_messages` 表中的 `feedback` 字段。

**Architecture:** 
1. 后端修改 SQLAlchemy `ChatMessage` 模型添加 `feedback` 列，支持 `none`/`like`/`dislike`/`collected`/`approved` 状态；
2. 新增 Pydantic 请求 Schema 并扩展 CRUD 更新层，在 `api.py` 中发布 `POST /api/chat/messages/{message_id}/feedback` 端点；
3. 前端扩展 `Message` 接口、API 请求与 Pinia Store 的 action，在 `MessageItem.vue` 中渲染点赞、点踩、收藏按钮并绑定点击回调。

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Vue 3, Pinia, TypeScript, Pytest, npm (vue-tsc).

---

### Task 1: 数据库模型与 Schema 改造

**Files:**
- Modify: `backend/app/models.py:31-50`
- Modify: `backend/app/schemas.py:8-42`
- Test: Modify `backend/app/test_api_persistence.py` (Add new test)

- [ ] **Step 1: 编写数据模型与 Schema 校验测试用例**
  在 [test_api_persistence.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/test_api_persistence.py) 底部添加以下测试函数：
  ```python
  def test_message_feedback_schema_and_model():
      """测试反馈相关的 Pydantic 校验和 SQLAlchemy 模型字段定义"""
      from backend.app.schemas import MessageResponse, MessageFeedbackRequest
      from backend.app.models import ChatMessage

      # 1. 验证 MessageFeedbackRequest 能够正确实例化
      req = MessageFeedbackRequest(feedback="collected")
      assert req.feedback == "collected"

      # 2. 验证 MessageResponse 支持 feedback 属性且默认值为 "none"
      res = MessageResponse(
          id="msg-1",
          role="assistant",
          content="hello",
          session_id="sess-1",
          feedback="collected",
          created_at="2026-06-29T10:00:00"
      )
      assert res.feedback == "collected"

      # 3. 验证 SQLAlchemy ChatMessage 模型具备 feedback 字段定义
      msg = ChatMessage(role="assistant", content="hello", session_id="sess-1")
      assert hasattr(msg, "feedback")
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py::test_message_feedback_schema_and_model -v`
  Expected: FAIL with `ImportError: cannot import name 'MessageFeedbackRequest'`

- [ ] **Step 3: 修改 backend/app/models.py 扩展 ChatMessage 字段**
  修改 [models.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/models.py) 的 `ChatMessage` 类，在 `created_at` 字段之前加入 `feedback` 列定义：
  ```python
  class ChatMessage(Base):
      __tablename__ = "chat_messages"
  
      id = Column(String(36), primary_key=True, index=True, default=generate_uuid)
      session_id = Column(
          String(36),
          ForeignKey("chat_sessions.id", ondelete="CASCADE"),
          nullable=False,
          index=True,
      )
      role = Column(
          String(50), nullable=False
      )  # e.g., 'user' or 'assistant' 'system' ''tool'
      content = Column(Text, nullable=False)
      tool_calls = Column(Text, nullable=True)  # 改为Text类型
      tool_results = Column(Text, nullable=True)  # 改为Text类型
      feedback = Column(String(50), nullable=False, default="none")  # 💡 新增反馈状态
      created_at = Column(DateTime, nullable=False, default=func.now())
  
      session = relationship("ChatSession", back_populates="messages")
  ```

- [ ] **Step 4: 修改 backend/app/schemas.py 新增反馈 Schema**
  在 [schemas.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/schemas.py) 中，首先修改 `MessageBase` 类（添加 `feedback` 列，默认 `"none"`）：
  ```python
  # 消息基类
  class MessageBase(BaseModel):
      role: str  # user, assistant, system, tool
      content: str
      session_id: str
      tool_calls: Optional[str] = None  # JSON字符串
      tool_results: Optional[str] = None  # JSON字符串
      feedback: str = "none"  # 💡 新增反馈状态，默认 "none"
  ```
  在 `schemas.py` 尾部添加 `MessageFeedbackRequest` 模型：
  ```python
  class MessageFeedbackRequest(BaseModel):
      """客户端提交赞/踩/收藏状态的请求体"""
      feedback: str  # 取值：none, like, dislike, collected, approved
  ```

- [ ] **Step 5: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py::test_message_feedback_schema_and_model -v`
  Expected: PASS

- [ ] **Step 6: Commit**
  ```bash
  git add backend/app/models.py backend/app/schemas.py backend/app/test_api_persistence.py
  git commit -m "feat: add feedback column to ChatMessage model and schemas"
  ```

---

### Task 2: CRUD 业务层接口实现

**Files:**
- Modify: `backend/app/crud.py:120-145`
- Test: Modify `backend/app/test_api_persistence.py` (Add new test)

- [ ] **Step 1: 编写 CRUD 接口校验测试用例**
  在 [test_api_persistence.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/test_api_persistence.py) 中追加 `test_update_message_feedback_crud`：
  ```python
  @patch("backend.app.crud.get_message")
  def test_update_message_feedback_crud(mock_get_message):
      """测试 crud.update_message_feedback 方法"""
      from backend.app.crud import update_message_feedback
      
      mock_msg = MagicMock()
      mock_msg.feedback = "none"
      mock_get_message.return_value = mock_msg
      
      mock_db = MagicMock()
      result = update_message_feedback(mock_db, "msg-123", "like")
      
      assert result.feedback == "like"
      mock_get_message.assert_called_once_with(mock_db, "msg-123")
      mock_db.commit.assert_called_once()
      mock_db.refresh.assert_called_once_with(mock_msg)
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py::test_update_message_feedback_crud -v`
  Expected: FAIL with `ImportError: cannot import name 'update_message_feedback'`

- [ ] **Step 3: 在 backend/app/crud.py 中实现更新方法**
  在 [crud.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/crud.py) 的 `get_message` 之后加入 `update_message_feedback` 函数：
  ```python
  def update_message_feedback(db: Session, message_id: str, feedback: str) -> Optional[ChatMessage]:
      """更新指定消息的反馈状态"""
      db_message = get_message(db, message_id)
      if db_message:
          db_message.feedback = feedback
          db.commit()
          db.refresh(db_message)
      return db_message
  ```

- [ ] **Step 4: 运行测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py::test_update_message_feedback_crud -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/crud.py backend/app/test_api_persistence.py
  git commit -m "feat: implement update_message_feedback CRUD method"
  ```

---

### Task 3: 后端 APIRouter 反馈路由发布

**Files:**
- Modify: `backend/app/api.py:300-330`
- Test: Modify `backend/app/test_api_persistence.py` (Add new test)

- [ ] **Step 1: 编写 API 接口测试用例**
  In [test_api_persistence.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/test_api_persistence.py) 中追加 `test_post_message_feedback_endpoint`：
  ```python
  from datetime import datetime
  
  @patch("backend.app.api.crud.update_message_feedback")
  def test_post_message_feedback_endpoint(mock_update_message_feedback):
      """测试 POST /api/chat/messages/{id}/feedback 接口"""
      mock_msg = MagicMock()
      mock_msg.id = "msg-123"
      mock_msg.role = "assistant"
      mock_msg.content = "hello"
      mock_msg.session_id = "sess-1"
      mock_msg.feedback = "like"
      mock_msg.created_at = datetime.now()
      mock_update_message_feedback.return_value = mock_msg
  
      client = TestClient(app)
      response = client.post(
          "/api/chat/messages/msg-123/feedback",
          json={"feedback": "like"}
      )
      assert response.status_code == 200
      assert response.json()["feedback"] == "like"
      mock_update_message_feedback.assert_called_once()
  ```

- [ ] **Step 2: 运行测试验证失败**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py::test_post_message_feedback_endpoint -v`
  Expected: FAIL with `404 Not Found`

- [ ] **Step 3: 在 backend/app/api.py 中编写路由接口**
  在 [api.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/backend/app/api.py) 中，首先在头部导入 Schema：
  ```python
  from .schemas import (
      # Session Schemas
      ChatRequest,
      ChatResponse,
      ChartArtifactResponse,
      serialize_chat_stream_event,
      SessionCreate,
      SessionUpdate,
      SessionResponse,
      # Message Schemas
      MessageCreate,
      MessageResponse,
      MessageFeedbackRequest,  # 💡 导入新增的反馈 Request Schema
  )
  ```
  在 `delete_message_endpoint` 之后添加路由定义：
  ```python
  @router.post("/messages/{message_id}/feedback", response_model=MessageResponse)
  def update_message_feedback_endpoint(
      message_id: str,
      feedback_request: MessageFeedbackRequest,
      db: Session = Depends(get_db)
  ):
      """更新特定消息的用户反馈状态 (like/dislike/collected/none)"""
      db_message = crud.update_message_feedback(db, message_id, feedback_request.feedback)
      if not db_message:
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail=f"消息 {message_id} 不存在"
          )
      return db_message
  ```

- [ ] **Step 4: 运行所有测试验证通过**
  Run: `conda activate py312_agent; pytest backend/app/test_api_persistence.py -v`
  Expected: 所有 7 个测试（包括原有流式中断等）全部 PASS

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/api.py backend/app/test_api_persistence.py
  git commit -m "feat: add POST feedback router to api.py"
  ```

---

### Task 4: 前端 API、类型与 Pinia Store 改造

**Files:**
- Modify: `frontend/src/types/index.ts:31-43`
- Modify: `frontend/src/api/messages.ts`
- Modify: `frontend/src/stores/messages.ts:70-85`

- [ ] **Step 1: 在前端类型中添加 feedback 属性**
  修改 [index.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/types/index.ts) 的 `Message` 接口，在 `questions` 之后追加反馈字段：
  ```typescript
  // 消息类型
  export interface Message {
    id: string
    role: 'user' | 'assistant' | 'system' | 'tool'
    content: string
    session_id: string
    created_at: string
    tool_calls?: string | null
    tool_results?: string | null
    is_interrupted?: boolean
    questions?: QuestionItem[]
    feedback?: 'none' | 'like' | 'dislike' | 'collected' | 'approved'  // 💡 反馈状态
  }
  ```

- [ ] **Step 2: 在前端 messages API 中导出提交方法**
  修改 [messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/api/messages.ts)，在末尾追加 `submitMessageFeedbackApi` 请求函数：
  ```typescript
  export const submitMessageFeedbackApi = (id: string, feedback: string): Promise<Message> => {
    return api.post(`/api/chat/messages/${id}/feedback`, { feedback })
  }
  ```

- [ ] **Step 3: 在 Pinia Store 中添加 feedback action 触发逻辑**
  修改 [messages.ts](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/stores/messages.ts)，首先在头部引入 API 方法：
  ```typescript
  import { getMessagesBySessionApi, createMessageApi, deleteMessageApi, submitMessageFeedbackApi } from '@/api/messages'
  ```
  在 `deleteMessage` Action 之后追加 `submitMessageFeedback` Action 方法：
  ```typescript
    const submitMessageFeedback = async (messageId: string, feedback: 'none' | 'like' | 'dislike' | 'collected' | 'approved') => {
    try {
      const updatedMessage = await submitMessageFeedbackApi(messageId, feedback)
      const index = messages.value.findIndex(m => m.id === messageId)
      if (index !== -1) {
        messages.value[index] = { ...messages.value[index], feedback: updatedMessage.feedback }
      }
    } catch (err) {
      console.error('提交消息反馈失败', err)
      throw err
    }
  }
  ```
  并在 store 底部的 return 块中导出该 action：
  ```typescript
    return {
      messages,
      streamingMessage,
      isStreaming,
      loading,
      error,
      fetchMessages,
      createMessage,
      deleteMessage,
      submitMessageFeedback,  // 💡 导出反馈 action
      clearMessages,
      // ...
    }
  ```

- [ ] **Step 4: 运行前端编译校验无 TypeScript 报错**
  Run: `cd frontend; npm run build:check`
  Expected: 编译无任何报错，打包输出成功

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src/types/index.ts frontend/src/api/messages.ts frontend/src/stores/messages.ts
  git commit -m "feat: add feedback property to Message interface and Pinia actions"
  ```

---

### Task 5: 前端 MessageItem 组件渲染与交互

**Files:**
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: 修改 MessageItem.vue 的模板部分，渲染赞/踩/收藏栏**
  修改 [MessageItem.vue](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent/frontend/src/components/MessageItem.vue) 模板的尾部时间展示结构（第 201-210 行），替换为带操作按钮与状态高亮绑定的反馈时间栏：
  ```vue
        <!-- 反馈操作按钮与时间状态展示行 -->
        <div
          v-if="!isUser && !isStreamingActive && props.message.id && !props.message.id.startsWith('temp-')"
          class="flex items-center justify-between px-5 pb-3.5 pt-0 text-neutral-400 border-t border-neutral-100/50 mt-1"
        >
          <div class="flex items-center gap-4 mt-2">
            <button
              type="button"
              class="transition-colors duration-150 hover:text-primary active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium"
              :class="{ 'text-primary !font-semibold': props.message.feedback === 'like' }"
              @click="handleFeedback('like')"
            >
              👍 <span class="hidden sm:inline">赞</span>
            </button>
            <button
              type="button"
              class="transition-colors duration-150 hover:text-rose-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium"
              :class="{ 'text-rose-500 !font-semibold': props.message.feedback === 'dislike' }"
              @click="handleFeedback('dislike')"
            >
              👎 <span class="hidden sm:inline">踩</span>
            </button>
            <button
              type="button"
              class="transition-colors duration-150 hover:text-amber-500 active:scale-95 flex items-center gap-1.5 text-xs text-neutral-500 font-medium"
              :class="{ 'text-amber-500 !font-semibold': props.message.feedback === 'collected' || props.message.feedback === 'approved' }"
              @click="handleFeedback(props.message.feedback === 'collected' || props.message.feedback === 'approved' ? 'none' : 'collected')"
            >
              ⭐ <span class="hidden sm:inline">{{ props.message.feedback === 'collected' || props.message.feedback === 'approved' ? '已收藏' : '收藏' }}</span>
            </button>
          </div>
          <div class="flex items-center gap-1 mt-2" :class="timeClass">
            <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-xs">{{ formattedTime }}</span>
          </div>
        </div>
        <div
          v-else
          class="flex items-center justify-end gap-1.5 px-5 pb-3.5 pt-0"
          :class="timeClass"
        >
          <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-xs">{{ formattedTime }}</span>
        </div>
  ```

- [ ] **Step 2: 修改 MessageItem.vue 的 script setup，编写点击动作逻辑**
  在 `MessageItem.vue` 中导入 Pinia Store，并定义点击事件。
  在 `<script setup>` 的 imports 中导入 store：
  ```typescript
  import { useMessagesStore } from '@/stores/messages'
  ```
  在组件定义的最底部，添加 Action 初始化与回调函数：
  ```typescript
  const messagesStore = useMessagesStore()
  
  const handleFeedback = async (feedbackType: 'none' | 'like' | 'dislike' | 'collected' | 'approved') => {
    if (!props.message.id) return
    try {
      await messagesStore.submitMessageFeedback(props.message.id, feedbackType)
    } catch (err) {
      console.error('Submit feedback failed:', err)
    }
  }
  ```

- [ ] **Step 3: 验证前端编译无报错**
  Run: `cd frontend; npm run build:check`
  Expected: 编译顺利通过，输出无报错

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/components/MessageItem.vue
  git commit -m "feat: implement thumbs and star interactive UI in MessageItem.vue"
  ```
