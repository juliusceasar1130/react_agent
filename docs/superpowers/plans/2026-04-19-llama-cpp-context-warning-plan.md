# Llama.cpp Context Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在使用 OpenAI-compatible `llama.cpp` API 时，为每次模型调用增加“调用前上下文 token 预警”，在接近配置阈值时提醒用户建议新建对话，但不做自动压缩、自动摘要或阻断。

**Architecture:** 后端新增一个只读 `ContextWarningMiddleware`，在最终 `ModelRequest` 形成后使用 `llama.cpp /tokenize` 估算本次输入上下文 token 数；达到阈值时生成统一的 `context_warning` payload，并通过流式 `status.detail` 与非流式响应同时透传给前端。前端仅做轻量提醒条展示，不改消息正文，不参与任何自动动作。

**Tech Stack:** FastAPI, LangChain AgentMiddleware, OpenAI-compatible llama.cpp server, Pydantic, Vue 3, TypeScript, Pinia

## Execution Status

- [x] Task 1 已完成：新增配置与 `llama.cpp /tokenize` 估算器，并补齐对应测试。
- [x] Task 2 已完成：新增 `ContextWarningMiddleware`，达到阈值时写入统一 `context_warning` payload。
- [x] Task 3 已完成：在 Agent 初始化链路中注册 middleware，位置位于 `SkillMiddleware` 之后。
- [x] Task 4 已完成：后端非流式响应与流式 `status.detail` 已透传 `context_warning`，并补充 API 侧测试。
- [x] Task 5 已完成：前端已消费 warning 状态并展示轻量预警条，`npm run build` 通过。
- [ ] Task 6 部分完成：`changelog.md` 已记录功能；`.env` 是否默认启用仍保留为本地部署决策，不在本次代码提交中强制改写。

---

## File Structure

**Create**
- `backend/app/agent/utils/llama_cpp_token_estimator.py`
  - 负责调用 `LLAMA_CPP_TOKENIZE_BASE_URL/tokenize`，返回文本 token 数；在接口异常时回退为保守估算。
- `backend/app/agent/middleware/context_warning_middleware.py`
  - 负责在 `ModelRequest` 级别估算 `system_message`、`messages`、`tools` 的输入 token，并在超阈值时写入预警结果。
- `docs/superpowers/plans/2026-04-19-llama-cpp-context-warning-plan.md`
  - 当前计划文档。

**Modify**
- `backend/app/config.py`
  - 新增上下文预警开关与阈值配置。
- `backend/app/agent/middleware/__init__.py`
  - 导出 `ContextWarningMiddleware`。
- `backend/app/agent/service.py`
  - 注册 `ContextWarningMiddleware`，并保持其位于 `SkillMiddleware` 之后。
- `backend/app/services.py`
  - 在流式 / 非流式链路中透传 `context_warning`。
- `backend/app/schemas.py`
  - 新增 `ContextWarningPayload`，扩展 `ChatResponse` 与流式 `status.detail` 约定。
- `backend/app/api.py`
  - 非流式接口返回 `context_warning`，流式接口在 SSE 中保留 `status.detail`。
- `frontend/src/types/index.ts`
  - 定义 `ContextWarningPayload`、扩展 `ChatResponse`、约束 `status.detail`。
- `frontend/src/composables/useChatStream.ts`
  - 接收 `context_warning` 状态并同步到界面态。
- `frontend/src/views/ChatView.vue`
  - 展示轻量预警条。

**Test**
- `backend/app/test_context_warning_middleware.py`
  - 测试估算触发阈值、关闭开关、tokenize 失败回退等行为。
- `backend/app/test_llama_cpp_token_estimator.py`
  - 测试 `/tokenize` 调用、超时与回退估算。

## Configuration Contract

一期仅保留显式开关，不做自动探测：

```env
LLM_CONTEXT_WARNING_ENABLED=false
LLM_CONTEXT_WINDOW=16384
LLM_CONTEXT_WARN_TOKENS=12000
LLM_CONTEXT_SAFETY_BUFFER=512
LLAMA_CPP_TOKENIZE_BASE_URL=http://192.168.3.245:8089
LLM_CONTEXT_TOKENIZER_TIMEOUT=5
```

含义：
- `LLM_CONTEXT_WARNING_ENABLED`: 唯一开关，`false` 时整套逻辑完全不运行。
- `LLM_CONTEXT_WINDOW`: 对应 `llama-server -c 16384`。
- `LLM_CONTEXT_WARN_TOKENS`: 预警阈值，达到即提醒。
- `LLM_CONTEXT_SAFETY_BUFFER`: 固定冗余，补偿 chat template / schema / role 包装等隐含开销。
- `LLAMA_CPP_TOKENIZE_BASE_URL`: 不带 `/v1` 的 `llama.cpp` 服务根地址。
- `LLM_CONTEXT_TOKENIZER_TIMEOUT`: 调用 `/tokenize` 的超时时间。

## Warning Payload Contract

```json
{
  "estimated_input_tokens": 12134,
  "warn_tokens": 12000,
  "context_window": 16384,
  "output_reserve": 2000,
  "safety_buffer": 512,
  "message_count": 9,
  "tool_count": 3,
  "recommended_action": "start_new_session",
  "source": "context_warning"
}
```

流式事件继续复用现有 `status` 类型：

```json
{
  "type": "status",
  "stage": "thinking",
  "text": "当前上下文已接近安全阈值，建议新建对话",
  "source": "context_warning",
  "detail": {
    "estimated_input_tokens": 12134,
    "warn_tokens": 12000,
    "context_window": 16384,
    "output_reserve": 2000,
    "safety_buffer": 512,
    "recommended_action": "start_new_session"
  }
}
```

---

### Task 1: Add Config And Token Estimator

**Files:**
- Create: `backend/app/agent/utils/llama_cpp_token_estimator.py`
- Modify: `backend/app/config.py`
- Test: `backend/app/test_llama_cpp_token_estimator.py`

- [ ] **Step 1: Write the failing estimator tests**

```python
from backend.app.agent.utils.llama_cpp_token_estimator import LlamaCppTokenEstimator


def test_count_text_tokens_uses_tokenize_endpoint(mocker):
    mock_post = mocker.patch("backend.app.agent.utils.llama_cpp_token_estimator.requests.post")
    mock_post.return_value.json.return_value = {"tokens": [1, 2, 3]}
    mock_post.return_value.raise_for_status.return_value = None

    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5,
        safety_buffer=512,
    )

    assert estimator.count_text_tokens("hello world") == 3


def test_count_text_tokens_falls_back_when_tokenize_fails(mocker):
    mocker.patch(
        "backend.app.agent.utils.llama_cpp_token_estimator.requests.post",
        side_effect=RuntimeError("boom"),
    )

    estimator = LlamaCppTokenEstimator(
        base_url="http://127.0.0.1:8089",
        timeout=5,
        safety_buffer=512,
    )

    assert estimator.count_text_tokens("abcdef") >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_llama_cpp_token_estimator.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.agent.utils.llama_cpp_token_estimator'
```

- [ ] **Step 3: Add config fields in `backend/app/config.py`**

```python
    llm_context_warning_enabled: bool = (
        os.getenv("LLM_CONTEXT_WARNING_ENABLED", "false").lower() == "true"
    )
    llm_context_window: int = int(os.getenv("LLM_CONTEXT_WINDOW", "16384"))
    llm_context_warn_tokens: int = int(os.getenv("LLM_CONTEXT_WARN_TOKENS", "12000"))
    llm_context_safety_buffer: int = int(os.getenv("LLM_CONTEXT_SAFETY_BUFFER", "512"))
    llama_cpp_tokenize_base_url: str = os.getenv(
        "LLAMA_CPP_TOKENIZE_BASE_URL", "http://127.0.0.1:8089"
    )
    llm_context_tokenizer_timeout: float = float(
        os.getenv("LLM_CONTEXT_TOKENIZER_TIMEOUT", "5")
    )
```

- [ ] **Step 4: Write minimal estimator implementation**

```python
from __future__ import annotations

import logging
from math import ceil
from typing import Any

import requests

logger = logging.getLogger(__name__)


class LlamaCppTokenEstimator:
    def __init__(self, base_url: str, timeout: float, safety_buffer: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.safety_buffer = safety_buffer

    def count_text_tokens(self, text: str) -> int:
        if not text:
            return 0

        payload = {
            "content": text,
            "add_special": False,
            "parse_special": True,
            "with_pieces": False,
        }
        try:
            response = requests.post(
                f"{self.base_url}/tokenize",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            tokens = response.json().get("tokens", [])
            return len(tokens) if isinstance(tokens, list) else 0
        except Exception as exc:
            logger.warning("llama.cpp /tokenize 调用失败，改用保守估算: %s", exc)
            return max(1, ceil(len(text) / 3))

    def count_json_like_tokens(self, value: Any) -> int:
        import json

        return self.count_text_tokens(json.dumps(value, ensure_ascii=False, sort_keys=True))
```

- [ ] **Step 5: Run tests to verify estimator passes**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_llama_cpp_token_estimator.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/agent/utils/llama_cpp_token_estimator.py backend/app/test_llama_cpp_token_estimator.py
git commit -m "feat: add llama.cpp token estimator"
```

### Task 2: Add Context Warning Middleware

**Files:**
- Create: `backend/app/agent/middleware/context_warning_middleware.py`
- Modify: `backend/app/agent/middleware/__init__.py`
- Test: `backend/app/test_context_warning_middleware.py`

- [ ] **Step 1: Write the failing middleware tests**

```python
from langchain.agents.middleware import ModelRequest
from langchain.messages import HumanMessage, SystemMessage

from backend.app.agent.middleware.context_warning_middleware import ContextWarningMiddleware
from backend.app.agent.utils.llama_cpp_token_estimator import LlamaCppTokenEstimator


def test_warning_is_created_when_threshold_reached(mocker):
    estimator = mocker.Mock(spec=LlamaCppTokenEstimator)
    estimator.count_text_tokens.side_effect = [50, 80]
    estimator.count_json_like_tokens.return_value = 20

    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=True,
        context_window=16384,
        warn_tokens=120,
        output_reserve=2000,
        safety_buffer=10,
    )

    request = ModelRequest(
        model="test-model",
        system_message=SystemMessage(content="system"),
        messages=[HumanMessage(content="user")],
        tools=[],
    )

    payload = middleware._build_warning_payload(request)
    assert payload is not None
    assert payload["recommended_action"] == "start_new_session"


def test_warning_is_skipped_when_feature_disabled(mocker):
    estimator = mocker.Mock(spec=LlamaCppTokenEstimator)
    middleware = ContextWarningMiddleware(
        estimator=estimator,
        enabled=False,
        context_window=16384,
        warn_tokens=12000,
        output_reserve=2000,
        safety_buffer=512,
    )

    request = mocker.Mock()
    assert middleware._build_warning_payload(request) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_context_warning_middleware.py -v
```

Expected:

```text
E   ModuleNotFoundError: No module named 'backend.app.agent.middleware.context_warning_middleware'
```

- [ ] **Step 3: Write minimal middleware implementation**

```python
from __future__ import annotations

from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse

from backend.app.agent.state import CustomState
from backend.app.agent.utils.llama_cpp_token_estimator import LlamaCppTokenEstimator


class ContextWarningMiddleware(AgentMiddleware[CustomState]):
    state_schema = CustomState

    def __init__(
        self,
        estimator: LlamaCppTokenEstimator,
        *,
        enabled: bool,
        context_window: int,
        warn_tokens: int,
        output_reserve: int,
        safety_buffer: int,
    ) -> None:
        self.estimator = estimator
        self.enabled = enabled
        self.context_window = context_window
        self.warn_tokens = warn_tokens
        self.output_reserve = output_reserve
        self.safety_buffer = safety_buffer

    def _build_warning_payload(self, request: ModelRequest) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        system_tokens = self.estimator.count_text_tokens(str(request.system_message.content))
        message_tokens = sum(
            self.estimator.count_text_tokens(str(message.content))
            for message in request.messages
        )
        tool_tokens = self.estimator.count_json_like_tokens(request.tools)
        estimated_input_tokens = system_tokens + message_tokens + tool_tokens + self.safety_buffer

        if estimated_input_tokens < self.warn_tokens:
            return None

        return {
            "estimated_input_tokens": estimated_input_tokens,
            "warn_tokens": self.warn_tokens,
            "context_window": self.context_window,
            "output_reserve": self.output_reserve,
            "safety_buffer": self.safety_buffer,
            "message_count": len(request.messages),
            "tool_count": len(request.tools or []),
            "recommended_action": "start_new_session",
            "source": "context_warning",
        }

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        payload = self._build_warning_payload(request)
        if payload is not None:
            request.runtime.context["context_warning"] = payload
        return await handler(request)
```

- [ ] **Step 4: Export middleware in `backend/app/agent/middleware/__init__.py`**

```python
from .context_warning_middleware import ContextWarningMiddleware
from .skill_middleware import SkillMiddleware
from .rag_middleware import BusinessRagMiddleware

__all__ = ["ContextWarningMiddleware", "SkillMiddleware", "BusinessRagMiddleware"]
```

- [ ] **Step 5: Run tests to verify middleware passes**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_context_warning_middleware.py -v
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/middleware/context_warning_middleware.py backend/app/agent/middleware/__init__.py backend/app/test_context_warning_middleware.py
git commit -m "feat: add context warning middleware"
```

### Task 3: Wire Middleware Into Agent Initialization

**Files:**
- Modify: `backend/app/agent/service.py`
- Test: `backend/app/test_agent_service_prompt.py`

- [ ] **Step 1: Write the failing registration test**

```python
from backend.app.agent.service import SQLAgentService


def test_context_warning_middleware_is_appended_when_enabled(mocker):
    service = SQLAgentService(use_ollama=False, managed_runtime=False, auto_initialize=False)
    mocker.patch("backend.app.agent.service._configure_proxy_settings")
    mocker.patch("backend.app.agent.service._create_llm", return_value=object())
    mocker.patch("backend.app.agent.service._create_database_connection", return_value=(object(), {}))
    mocker.patch("backend.app.agent.service._prepare_tools", return_value=[])
    mocker.patch("backend.app.agent.service._build_system_prompt", return_value="prompt")
    mocker.patch("backend.app.agent.service._create_business_retriever_and_reranker", return_value=(None, None))
    mocker.patch("backend.app.agent.service.settings.llm_context_warning_enabled", True)
    mock_create_agent = mocker.patch("backend.app.agent.service.create_agent")
    mocker.patch.object(service, "_ainitialize_persistence", return_value=None)

    import asyncio
    asyncio.run(service._ainitialize_agent())

    middleware = mock_create_agent.call_args.kwargs["middleware"]
    assert middleware[-1].__class__.__name__ == "ContextWarningMiddleware"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_agent_service_prompt.py -k context_warning -v
```

Expected:

```text
FAILED ... AssertionError
```

- [ ] **Step 3: Register `ContextWarningMiddleware` in both sync and async init paths**

```python
            context_warning_middleware = ContextWarningMiddleware(
                estimator=LlamaCppTokenEstimator(
                    base_url=settings.llama_cpp_tokenize_base_url,
                    timeout=settings.llm_context_tokenizer_timeout,
                    safety_buffer=settings.llm_context_safety_buffer,
                ),
                enabled=settings.llm_context_warning_enabled,
                context_window=settings.llm_context_window,
                warn_tokens=settings.llm_context_warn_tokens,
                output_reserve=settings.agent_max_tokens,
                safety_buffer=settings.llm_context_safety_buffer,
            )

            middleware_list = [summarization_middleware, SkillMiddleware(), context_warning_middleware]
```

- [ ] **Step 4: Run targeted test**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_agent_service_prompt.py -k context_warning -v
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/service.py backend/app/test_agent_service_prompt.py
git commit -m "feat: register context warning middleware"
```

### Task 4: Expose Warning Through API And Stream Events

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services.py`
- Modify: `backend/app/api.py`
- Test: `backend/app/test_chart_api.py`

- [ ] **Step 1: Write failing schema/API tests**

```python
from backend.app.schemas import ChatResponse


def test_chat_response_accepts_context_warning():
    payload = ChatResponse.model_validate(
        {
            "session_id": "s1",
            "message": {
                "id": "m1",
                "role": "assistant",
                "content": "ok",
                "session_id": "s1",
                "created_at": "2026-04-19T00:00:00",
            },
            "is_complete": True,
            "context_warning": {
                "estimated_input_tokens": 12001,
                "warn_tokens": 12000,
                "context_window": 16384,
                "output_reserve": 2000,
                "safety_buffer": 512,
                "message_count": 8,
                "tool_count": 2,
                "recommended_action": "start_new_session",
                "source": "context_warning",
            },
        }
    )
    assert payload.context_warning is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_chart_api.py -k context_warning -v
```

Expected:

```text
FAILED ... ValidationError
```

- [ ] **Step 3: Add `ContextWarningPayload` and response fields**

```python
class ContextWarningPayload(BaseModel):
    estimated_input_tokens: int
    warn_tokens: int
    context_window: int
    output_reserve: int
    safety_buffer: int
    message_count: int
    tool_count: int
    recommended_action: Literal["start_new_session"]
    source: Literal["context_warning"]


class ChatResponse(BaseModel):
    session_id: str
    message: MessageResponse
    is_complete: bool = True
    context_warning: Optional[ContextWarningPayload] = None
```

- [ ] **Step 4: Pass warning through service and API layers**

```python
        return {
            "content": content,
            "tool_calls": json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            "tool_results": json.dumps(tool_results, ensure_ascii=False) if tool_results else None,
            "context_warning": resolved_config.get("metadata", {}).get("context_warning"),
        }
```

```python
                    final_event = {
                        **event,
                        "content": assistant_message.content,
                        "tool_calls": final_tool_calls,
                        "tool_results": final_tool_results,
                        "message_id": assistant_message.id,
                        "created_at": assistant_message.created_at.isoformat(),
                    }
```

```python
    return ChatResponse(
        session_id=session_id,
        message=assistant_message,
        is_complete=True,
        context_warning=agent_response.get("context_warning"),
    )
```

- [ ] **Step 5: Run tests**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_chart_api.py -k context_warning -v
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/services.py backend/app/api.py backend/app/test_chart_api.py
git commit -m "feat: expose context warning in api responses"
```

### Task 5: Show Warning In Frontend

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/composables/useChatStream.ts`
- Modify: `frontend/src/views/ChatView.vue`

- [ ] **Step 1: Extend frontend types**

```ts
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

export interface ChatResponse {
  session_id: string
  message: Message
  is_complete: boolean
  context_warning?: ContextWarningPayload | null
}
```

- [ ] **Step 2: Add warning state in chat composable**

```ts
const contextWarning = ref<ContextWarningPayload | null>(null)

const clearContextWarning = () => {
  contextWarning.value = null
}
```

```ts
        case 'status':
          messagesStore.updateStreamingStatus(event.stage, event.text)
          if (event.source === 'context_warning' && event.detail) {
            contextWarning.value = event.detail as ContextWarningPayload
          }
          return
```

```ts
    const response = await sendChatMessage({
      message: content,
      session_id: sessionId,
      stream: false
    })
    contextWarning.value = response.context_warning ?? null
```

- [ ] **Step 3: Render warning bar in `ChatView.vue`**

```vue
      <div
        v-if="contextWarning"
        class="px-6 py-3 bg-amber-50 border-b border-amber-200 text-amber-800 text-sm"
      >
        当前上下文已接近安全阈值，建议新建对话
        (估算输入 {{ contextWarning.estimated_input_tokens }} / {{ contextWarning.warn_tokens }})
      </div>
```

```ts
const { isSending, streamMode, sendMessage, stopStreaming, contextWarning } = useChatStream()
```

- [ ] **Step 4: Run frontend build to verify types**

Run:

```bash
cd frontend
npm run build
```

Expected:

```text
vite build completed successfully
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/composables/useChatStream.ts frontend/src/views/ChatView.vue
git commit -m "feat: show context warning in chat ui"
```

### Task 6: End-To-End Verification And Docs

**Files:**
- Modify: `.env`
- Modify: `changelog.md`

- [ ] **Step 1: Add local config entries**

```env
LLM_CONTEXT_WARNING_ENABLED=true
LLM_CONTEXT_WINDOW=16384
LLM_CONTEXT_WARN_TOKENS=12000
LLM_CONTEXT_SAFETY_BUFFER=512
LLAMA_CPP_TOKENIZE_BASE_URL=http://192.168.3.245:8089
LLM_CONTEXT_TOKENIZER_TIMEOUT=5
```

- [ ] **Step 2: Run backend targeted tests**

Run:

```bash
conda run -n py312_agent pytest backend/app/test_llama_cpp_token_estimator.py backend/app/test_context_warning_middleware.py -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 3: Run manual smoke test**

Run:

```powershell
Invoke-RestMethod -Uri "http://192.168.3.245:8089/tokenize" -Method Post -ContentType "application/json" -Body (@{
  content = "hello world"
  add_special = $false
  parse_special = $true
  with_pieces = $false
} | ConvertTo-Json)
```

Expected:

```text
tokens length > 0
```

- [ ] **Step 4: Append changelog entry**

```markdown
## 2026-04-19 14:43:54 +08:00

- 新增 llama.cpp 上下文预警能力，可在单次模型调用接近安全阈值时提醒用户建议新建对话。
- 预警逻辑仅在 `LLM_CONTEXT_WARNING_ENABLED=true` 时启用，不影响其他模型接入。
```

- [ ] **Step 5: Commit**

```bash
git add .env changelog.md
git commit -m "docs: record llama.cpp context warning configuration"
```

## Self-Review

- **Spec coverage:** 已覆盖配置开关、`/tokenize` 估算器、`ModelRequest` 级中间件、后端透传、前端提示与验证收尾。
- **Placeholder scan:** 计划中未使用 `TODO/TBD`，每个任务都给出了文件路径、命令和最小代码骨架。
- **Type consistency:** 统一使用 `ContextWarningPayload`、`context_warning`、`recommended_action="start_new_session"` 这一套命名，没有混用别名。

Plan complete and saved to `docs/superpowers/plans/2026-04-19-llama-cpp-context-warning-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
