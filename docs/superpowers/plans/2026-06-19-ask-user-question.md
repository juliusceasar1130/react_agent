# AskUserQuestion Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a structural choice-and-answer tool (`AskUserQuestion`) using LangGraph 1.1.8's native `interrupt` control flow in the FastAPI backend, and render interactive question cards with Master-Detail code preview panels in the Vue 3 frontend matching the Light Mode Workspace theme.

**Architecture:** The agent triggers the tool which calls LangGraph's `interrupt()`, halting the graph and persisting state in `PostgresSaver`. The FastAPI backend catches the interrupt, yields a SSE event of type `interrupt` to Vue 3, and closes the connection. When the user responds, a new POST request to `/api/chat/resume` updates the thread state and resumes execution via `Command(resume=answers)`.

**Tech Stack:** FastAPI, LangGraph (1.1.8), LangChain (1.2.15), Vue 3 (Composition API), Pinia, Tailwind CSS.

---

### Task 1: Backend AskUserQuestion Tool Development

**Files:**
- Create: `backend/app/agent/tools/ask_user_question.py`
- Create: `backend/app/agent/tools/test_ask_user_question.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/agent/tools/test_ask_user_question.py` with tests verifying that the tool raises `GraphInterrupt` or `NodeInterrupt` when called:

```python
import pytest
from langgraph.errors import GraphInterrupt
from backend.app.agent.tools.ask_user_question import AskUserQuestion

def test_ask_user_question_raises_interrupt():
    tool = AskUserQuestion()
    questions_payload = [
        {
            "question": "Which indexing option to use?",
            "header": "Performance Tuning",
            "multiSelect": False,
            "options": [
                {"label": "B-Tree", "description": "Standard B-Tree Index", "preview": "CREATE INDEX..."}
            ]
        }
    ]
    with pytest.raises(GraphInterrupt) as excinfo:
        tool.invoke({"questions": questions_payload})
    
    assert excinfo.value.args[0][0]["value"]["type"] == "ask_user_question"
    assert excinfo.value.args[0][0]["value"]["questions"] == questions_payload
```

- [ ] **Step 2: Run test to verify it fails**

Run command:
`conda run -n py312_agent pytest backend/app/agent/tools/test_ask_user_question.py -v`

Expected output: `ModuleNotFoundError: No module named 'backend.app.agent.tools.ask_user_question'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/agent/tools/ask_user_question.py`:

```python
from typing import List, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.types import interrupt

class QuestionOption(BaseModel):
    label: str = Field(description="选项标签文本")
    description: Optional[str] = Field(None, description="选项的详细描述")
    preview: Optional[str] = Field(None, description="右侧对比栏的 Markdown 代码/配置预览")

class QuestionItem(BaseModel):
    question: str = Field(description="具体的澄清提问")
    header: Optional[str] = Field(None, description="卡片头分类信息")
    multiSelect: bool = Field(False, description="是否支持多选")
    options: List[QuestionOption] = Field(description="备选项列表，推荐 2~4 个")

class AskUserQuestionSchema(BaseModel):
    questions: List[QuestionItem] = Field(description="澄清问题卡片列表，支持 1~4 个")

class AskUserQuestion(BaseTool):
    name: str = "AskUserQuestion"
    description: str = (
        "当需求不明确、需要用户做出技术权衡、或者执行危险查询前需用户拍板时调用。"
        "向用户呈现结构化的选项或文本问答卡片。"
    )
    args_schema: Type[BaseModel] = AskUserQuestionSchema

    def _run(self, questions: List[dict]) -> dict:
        answers = interrupt({
            "type": "ask_user_question",
            "questions": questions
        })
        return answers
```

- [ ] **Step 4: Run test to verify it passes**

Run command:
`conda run -n py312_agent pytest backend/app/agent/tools/test_ask_user_question.py -v`

Expected output: `1 passed in ... seconds`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools/ask_user_question.py backend/app/agent/tools/test_ask_user_question.py
git commit -m "feat(agent): add AskUserQuestion tool with LangGraph interrupt"
```

---

### Task 2: Service Layer Tool Integration & Resume Handling

**Files:**
- Modify: `backend/app/agent/service.py`
- Modify: `backend/app/services.py`
- Create: `backend/app/agent/test_service_interrupt.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/agent/test_service_interrupt.py` to verify that `process_stream_resume` can resume an execution paused on `AskUserQuestion`:

```python
import pytest
from langgraph.types import Command
from backend.app.services import SQLAgentService

@pytest.mark.asyncio
async def test_agent_resume_process():
    # Mocking standard SQLAgentService state and invoking with Command
    # Verify process_stream_resume continues execution stream
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run command:
`conda run -n py312_agent pytest backend/app/agent/test_service_interrupt.py -v`

Expected output: Failures/AttributeError because `process_stream_resume` is not defined in `SQLAgentService`.

- [ ] **Step 3: Write minimal implementation**

**A. In `backend/app/agent/service.py`:**
Import `AskUserQuestion` and add it to `_prepare_tools`:
```python
# Near top imports:
from backend.app.agent.tools.ask_user_question import AskUserQuestion

# Inside _prepare_tools():
    tools.append(AskUserQuestion())
    logger.info("已注入澄清与确认工具：AskUserQuestion")
```

Update system prompt inside `_build_system_prompt()`:
```markdown
# 澄清与选择确认 (AskUserQuestion)
- 当面临需求不明确（如统计的业务口径有歧义）或需要用户权衡查询性能时，必须使用 AskUserQuestion 工具。
- 一次提问建议将所有相关问题进行批处理（1-4个问题，每个问题2-4个选项）。
- 必须将最推荐的方案放在第一个选项，且选项 label 追加 "(Recommended)" 后缀。
- 禁止针对普通的 SQL 错误向用户提问，必须自主调试解决。
```

**B. In `backend/app/services.py`:**
Add the resume processing helper to `SQLAgentService`:
```python
    async def process_stream_resume(
        self, session_id: str, answers: dict[str, Any], config: dict = None
    ) -> AsyncIterator[dict[str, Any]]:
        """从挂起状态恢复流式执行。"""
        resolved_config = self._build_config(
            session_id,
            config,
            request_mode="stream",
        )
        logger.info("正在恢复会话 %s 运行，传入用户答复: %s", session_id, answers)

        has_stream_tokens = False
        accumulated_tool_calls: dict[str, dict[str, Any]] = {}
        accumulated_tool_results: dict[str, str] = {}
        context_warning: Optional[dict[str, Any]] = None
        latest_ai_content = ""
        last_status_signature = None
        event_queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()
        stream_done = object()

        async def _emit(event: dict[str, Any]) -> None:
            await event_queue.put(event)

        async def _produce_events() -> None:
            nonlocal has_stream_tokens, latest_ai_content, last_status_signature, context_warning
            try:
                # 恢复迭代：传入 Command(resume=answers) 代替 HumanMessage
                source_iter = self.agent.astream(
                    Command(resume=answers),
                    config=resolved_config,
                    stream_mode=["messages", "updates", "custom"],
                    version="v2",
                )
                # Re-use identical chunk emission loop as in process_stream
                async for chunk in source_iter:
                    # ... chunk parsing ... (Copy logic from lines 638-780)
                    pass

                final_content = latest_ai_content
                tool_calls = self._serialize_tool_calls(accumulated_tool_calls, final=True)
                await _emit({
                    "type": "final",
                    "content": final_content,
                    "tool_calls": tool_calls or None,
                    "tool_results": accumulated_tool_results or None,
                    "context_warning": context_warning,
                })
            except Exception as exc:
                logger.error("恢复流式处理失败: %s", exc, exc_info=True)
                await _emit({"type": "error", "message": f"错误: {exc}", "retryable": False})
            finally:
                await event_queue.put(stream_done)

        producer_task = asyncio.create_task(_produce_events())
        try:
            while True:
                event = await event_queue.get()
                if event is stream_done:
                    break
                yield event
        finally:
            with suppress(asyncio.CancelledError):
                producer_task.cancel()
                await producer_task
```

Update `process_stream()`'s try-except block in `backend/app/services.py` to yield `interrupt` events when state.next lists interrupts:
```python
# At end of _produce_events in process_stream:
                state = await self.agent.aget_state(resolved_config)
                if state.next and any("tools" in n or "AskUserQuestion" in n for n in state.next):
                    # Check if the active interrupt belongs to AskUserQuestion
                    if state.tasks and state.tasks[0].interrupts:
                        interrupt_val = state.tasks[0].interrupts[0].value
                        if isinstance(interrupt_val, dict) and interrupt_val.get("type") == "ask_user_question":
                            await _emit({
                                "type": "interrupt",
                                "questions": interrupt_val.get("questions", []),
                                "session_id": session_id
                            })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n py312_agent pytest backend/app/agent/test_service_interrupt.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/service.py backend/app/services.py
git commit -m "feat(services): implement process_stream_resume and interrupt SSE extraction"
```

---

### Task 3: API Resume Route Development

**Files:**
- Modify: `backend/app/api.py`
- Create: `backend/app/test_api_resume.py`

- [ ] **Step 1: Write the failing test**

Create `backend/app/test_api_resume.py`:

```python
import pytest
from fastapi.testclient import TestClient
from backend.app.api import router

def test_resume_endpoint_not_found():
    # Make a post to /api/chat/resume and verify it returns HTTP 404/422 before route is declared
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n py312_agent pytest backend/app/test_api_resume.py`
Expected: Failures/HTTP status mismatch.

- [ ] **Step 3: Write minimal implementation**

**In `backend/app/api.py`:**
Add the `ResumeChatRequest` schema and `/resume` route:
```python
from pydantic import BaseModel

class ResumeChatRequest(BaseModel):
    session_id: str
    answers: dict[str, Any]

@router.post("/resume")
async def resume_chat_stream(
    chat_request: ResumeChatRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """从挂起状态恢复流式消息传输 (POST方法)"""
    logger.info("Received resume request via POST")
    session_id = chat_request.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id不能为空")

    session = crud.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    agent_service = get_agent_service()

    async def generate():
        stream_iter = agent_service.process_stream_resume(
            session_id,
            chat_request.answers,
            config={"configurable": {"thread_id": str(session_id)}}
        )
        # Identical client cancellation check & event yield loop as in stream_message_post
        # yielding _encode_sse(event)
        # yielding "data: [DONE]\n\n" at end
        pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n py312_agent pytest backend/app/test_api_resume.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api.py
git commit -m "feat(api): add /api/chat/resume endpoint for streaming resumption"
```

---

### Task 4: Frontend Types & Pinia Store Update

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/stores/messages.ts`

- [ ] **Step 1: Write mock assertions for Pinia store**

Write a quick test spec or dry run to assert that `isInterrupted` state exists on store instances.

- [ ] **Step 2: Modify frontend types in `frontend/src/types/index.ts`**

Add core interfaces:
```typescript
export interface QuestionOption {
  label: string;
  description?: string;
  preview?: string;
}

export interface QuestionItem {
  question: string;
  header?: string;
  multiSelect: boolean;
  options: QuestionOption[];
}

export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  tool_calls?: string | null;
  tool_results?: string | null;
  // Extended fields:
  is_interrupted?: boolean;
  questions?: QuestionItem[];
  answers?: string | null; // Save submitted results
}

export type StreamEvent =
  | { type: 'token'; text: string; node?: string }
  | { type: 'status'; stage: string; text: string; source: string; detail?: any }
  | { type: 'tool_call'; id: string; name: string; args_text: string; status: string }
  | { type: 'tool_result'; id: string; content: string }
  | { type: 'final'; message_id: string; created_at: string; content: string; tool_calls?: string | null; tool_results?: string | null }
  | { type: 'error'; message_id: string; created_at: string; message: string }
  | { type: 'interrupt'; questions: QuestionItem[]; session_id: string };
```

- [ ] **Step 3: Update `frontend/src/stores/messages.ts`**

Inject the states and actions:
```typescript
export const useMessagesStore = defineStore('messages', () => {
  const messages = ref<Message[]>([])
  
  // Interruption cache state
  const isInterrupted = ref(false)
  const pendingQuestions = ref<QuestionItem[]>([])
  const activeMessageId = ref<string | null>(null)

  function setInterruptedState(questions: QuestionItem[], messageId: string) {
    isInterrupted.value = true
    pendingQuestions.value = questions
    activeMessageId.value = messageId
    
    // Find the streaming message and save questions to it
    const msg = messages.value.find(m => m.id === messageId)
    if (msg) {
      msg.is_interrupted = true
      msg.questions = questions;
    }
  }

  function clearInterruptedState() {
    isInterrupted.value = false
    pendingQuestions.value = []
    activeMessageId.value = null
  }

  function setInterruptedAnswers(messageId: string, answers: Record<string, any>) {
    const msg = messages.value.find(m => m.id === messageId)
    if (msg) {
      msg.is_interrupted = false;
      msg.answers = JSON.stringify(answers);
    }
  }
  
  // Ensure that completes/errors also clear pending questions if they fail out
  // ...
  return {
    messages,
    isInterrupted,
    pendingQuestions,
    activeMessageId,
    setInterruptedState,
    clearInterruptedState,
    setInterruptedAnswers,
    // ...
  }
})
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/stores/messages.ts
git commit -m "feat(frontend): support interrupt types and message state updates in Pinia"
```

---

### Task 5: Frontend Composable & API Integration

**Files:**
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/composables/useChatStream.ts`

- [ ] **Step 1: Declare API and handler changes**

In `frontend/src/api/chat.ts`, add:
```typescript
export async function sendChatResumeStream(
  data: { session_id: string; answers: Record<string, any> },
  onEvent: (event: StreamEvent) => void,
  options?: { signal?: AbortSignal }
) {
  // Leverage same fetchSSE / EventSource connection to POST /api/chat/resume
}
```

- [ ] **Step 2: Update `useChatStream.ts` to support resumption**

```typescript
// Inside handleStreamMessage handler case logic:
        case 'interrupt':
          hasTerminalEvent = true // End initial SSE
          messagesStore.setInterruptedState(event.questions, messagesStore.streamingMessage.id)
          return

// Add resumeMessage helper in useChatStream:
  const resumeMessage = async (answers: Record<string, any>) => {
    const currentSession = sessionsStore.currentSession
    if (!currentSession) return

    isSending.value = true
    const messageId = messagesStore.activeMessageId

    // Record local answers & Clear interruption cache
    if (messageId) {
      messagesStore.setInterruptedAnswers(messageId, answers)
    }
    messagesStore.clearInterruptedState()

    const controller = new AbortController()
    activeStreamController.value = controller

    const handleEvent = (event: StreamEvent) => {
      // Direct stream updates (token appending) into the active message
      if (event.type === 'token' && event.text) {
        messagesStore.appendStreamingContent(event.text)
      } else if (event.type === 'final') {
        messagesStore.completeStreamingMessage({
          id: event.message_id,
          created_at: event.created_at,
          content: event.content,
          tool_calls: event.tool_calls ? JSON.stringify(event.tool_calls) : null,
          tool_results: event.tool_results ? JSON.stringify(event.tool_results) : null,
        })
      }
      // ... cover other cases (status, tool_call, error) ...
    }

    try {
      await sendChatResumeStream(
        { session_id: currentSession.id, answers },
        handleEvent,
        { signal: controller.signal }
      )
    } catch (error) {
      console.error('Failed to resume stream:', error)
    } finally {
      isSending.value = false
      activeStreamController.value = null
    }
  }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/chat.ts frontend/src/composables/useChatStream.ts
git commit -m "feat(frontend): integrate sendChatResumeStream and resumeMessage into useChatStream"
```

---

### Task 6: Card UI Component Implementation & Integration

**Files:**
- Create: `frontend/src/components/AskUserQuestionCard.vue`
- Modify: `frontend/src/components/MessageItem.vue`

- [ ] **Step 1: Create `AskUserQuestionCard.vue`**

Implement complete Vue component matching the **Light Mode Card-based Workspace** style:

```vue
<!-- frontend/src/components/AskUserQuestionCard.vue -->
<template>
  <div class="glass shadow-md rounded-2xl p-5 my-3 animate-slide-up transition-all duration-300">
    <div class="flex items-center gap-2 border-b border-neutral-100 pb-3 mb-4">
      <span class="text-lg">💡</span>
      <h4 class="text-sm font-semibold text-slate-700 tracking-wider">开发路径确认 (Orchestration Review)</h4>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      <!-- Left Column: Options Form -->
      <div :class="[hasPreview ? 'lg:col-span-6' : 'lg:col-span-12', 'space-y-5']">
        <div v-for="(q, qIdx) in questions" :key="qIdx" class="space-y-2">
          <div class="text-sm font-medium text-slate-800">{{ q.question }}</div>

          <!-- Options -->
          <div class="space-y-2">
            <div 
              v-for="(opt, optIdx) in q.options" 
              :key="optIdx"
              class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-200"
              :class="[
                isOptionSelected(qIdx, opt.label)
                  ? 'border-primary bg-primary/5 text-primary' 
                  : 'border-neutral-200 bg-white text-slate-700 hover:border-neutral-400'
              ]"
              @click="selectOption(qIdx, opt.label)"
              @mouseenter="hoveredPreview = opt.preview || null"
            >
              <input 
                :type="q.multiSelect ? 'checkbox' : 'radio'" 
                :checked="isOptionSelected(qIdx, opt.label)"
                :disabled="isSubmitted"
                class="mt-1 rounded border-neutral-300 text-primary focus:ring-primary/20"
                @click.stop
                @change="selectOption(qIdx, opt.label)"
              />
              <div class="flex-1">
                <div class="font-medium text-xs flex items-center gap-1.5">
                  {{ opt.label }}
                  <span v-if="opt.label.includes('(Recommended)')" class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold">推荐</span>
                </div>
                <div v-if="opt.description" class="text-[11px] text-neutral-400 mt-0.5">{{ opt.description }}</div>
              </div>
            </div>
          </div>

          <!-- Textarea Fallback -->
          <div class="space-y-1">
            <label class="text-[11px] text-neutral-400">补充描述或自定义要求 (将清除已有选择)</label>
            <textarea 
              v-model="freeTexts[qIdx]"
              :disabled="isSubmitted"
              placeholder="请输入自定义的反馈或要求..."
              class="w-full text-xs bg-white border border-neutral-200 rounded-xl p-2 focus:border-primary/80 focus:ring-1 focus:ring-primary/10"
              rows="2"
              @input="onFreeTextInput(qIdx)"
            ></textarea>
          </div>
        </div>

        <button 
          v-if="!isSubmitted"
          @click="submitAnswers" 
          :disabled="!isValid"
          class="btn-primary w-full text-xs text-center flex items-center justify-center"
        >
          提交决策并继续生成
        </button>
      </div>

      <!-- Right Column: Code/Markdown Preview Panel -->
      <div v-if="hasPreview" class="lg:col-span-6 border-t lg:border-t-0 lg:border-l border-neutral-100 pt-4 lg:pt-0 lg:pl-5 flex flex-col h-[320px]">
        <div class="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">🔍 方案代码对比</div>
        <div class="flex-1 bg-slate-900 border border-slate-700 rounded-2xl p-4 overflow-y-auto font-mono text-xs text-neutral-200">
          <div v-if="hoveredPreview || activePreview" class="message-markdown">
            <pre><code>{{ hoveredPreview || activePreview }}</code></pre>
          </div>
          <div v-else class="text-neutral-500 flex items-center justify-center h-full text-xs">
            悬停或点击选项查看代码/架构差异
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  questions: any[]
  isSubmitted: boolean
  submittedAnswers?: Record<string, any>
  onSubmit?: (answers: Record<string, any>) => void
}>()

const selectedAnswers = ref<Record<number, string[]>>({})
const freeTexts = ref<Record<number, string>>({})
const hoveredPreview = ref<string | null>(null)

// Initialize if submittedAnswers was loaded from history
if (props.isSubmitted && props.submittedAnswers) {
  props.questions.forEach((q, idx) => {
    const ans = props.submittedAnswers[q.question]
    if (Array.isArray(ans)) {
      selectedAnswers.value[idx] = ans
    } else if (ans) {
      // Check if it matches an option or is text
      const optMatch = q.options.some(o => o.label === ans)
      if (optMatch) {
        selectedAnswers.value[idx] = [ans]
      } else {
        freeTexts.value[idx] = ans
      }
    }
  })
}

const activePreview = computed(() => {
  for (let qIdx = 0; qIdx < props.questions.length; qIdx++) {
    const selected = selectedAnswers.value[qIdx] || []
    if (selected.length > 0) {
      const option = props.questions[qIdx].options.find(o => o.label === selected[0])
      if (option?.preview) return option.preview
    }
  }
  return null
})

const hasPreview = computed(() => {
  return props.questions.some(q => q.options.some(o => o.preview))
})

const isOptionSelected = (qIdx: number, label: string) => {
  return (selectedAnswers.value[qIdx] || []).includes(label)
}

const selectOption = (qIdx: number, label: string) => {
  if (props.isSubmitted) return
  freeTexts.value[qIdx] = ''
  
  const isMulti = props.questions[qIdx].multiSelect
  if (!selectedAnswers.value[qIdx]) {
    selectedAnswers.value[qIdx] = []
  }
  
  if (isMulti) {
    const idx = selectedAnswers.value[qIdx].indexOf(label)
    if (idx > -1) {
      selectedAnswers.value[qIdx].splice(idx, 1)
    } else {
      selectedAnswers.value[qIdx].push(label)
    }
  } else {
    selectedAnswers.value[qIdx] = [label]
  }
}

const onFreeTextInput = (qIdx: number) => {
  selectedAnswers.value[qIdx] = []
}

const isValid = computed(() => {
  return props.questions.every((_, idx) => {
    const hasSelections = (selectedAnswers.value[idx] || []).length > 0
    const hasCustomText = (freeTexts.value[idx] || '').trim().length > 0
    return hasSelections || hasCustomText
  })
})

const submitAnswers = () => {
  if (!isValid.value || props.isSubmitted || !props.onSubmit) return
  
  const formattedAnswers: Record<string, any> = {}
  props.questions.forEach((q, idx) => {
    const selections = selectedAnswers.value[idx] || []
    const text = freeTexts.value[idx] || ''
    
    if (text.trim()) {
      formattedAnswers[q.question] = text
    } else {
      formattedAnswers[q.question] = q.multiSelect ? selections : selections[0]
    }
  })
  
  props.onSubmit(formattedAnswers)
}
</script>
```

- [ ] **Step 2: Render Card inside `MessageItem.vue`**

Add the card rendering block inside `frontend/src/components/MessageItem.vue`:
```vue
<!-- Near other helper cards (e.g. charts) inside MessageItem.vue template -->
<AskUserQuestionCard
  v-if="message.questions && message.questions.length > 0"
  :questions="message.questions"
  :is-submitted="!!message.answers || !message.is_interrupted"
  :submitted-answers="message.answers ? JSON.parse(message.answers) : undefined"
  @submit="handleQuestionSubmit"
/>
```

Inside `<script setup>`:
```typescript
import AskUserQuestionCard from './AskUserQuestionCard.vue'

const emit = defineEmits(['resume-chat']) // Emit upwards or call useChatStream directly

const handleQuestionSubmit = (answers: Record<string, any>) => {
  // Emit state resume upwards to ChatView / useChatStream resume method
  emit('resume-chat', answers)
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AskUserQuestionCard.vue frontend/src/components/MessageItem.vue
git commit -m "feat(frontend): build AskUserQuestionCard and integrate inside MessageItem"
```
