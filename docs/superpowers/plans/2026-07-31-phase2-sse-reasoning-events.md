# Phase 2: 后端 SSE 流式协议与结构化思考事件扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose LLM reasoning tokens in real-time over SSE by adding `ReasoningStreamEvent` to `schemas.py` and processing `additional_kwargs["reasoning_content"]` in `services.py` streaming loop.

**Architecture:** Extend backend schema with `ReasoningStreamEvent`, inspect `message_chunk.additional_kwargs` in `services.py` `_stream_execution_loop`, and yield `type: "reasoning"` SSE events to clients without affecting standard token streaming.

**Tech Stack:** FastAPI, Pydantic v2, LangChain `AIMessageChunk`, SSE (`astream`), Pytest.

---

### File Structure & Responsibilities

- Modify: `backend/app/schemas.py`
  - Define `ReasoningStreamEvent(BaseModel)` with `{ type: Literal["reasoning"], text: str, node: Optional[str] }`
  - Add `ReasoningStreamEvent` to `ChatStreamEvent` discriminated union.
- Modify: `backend/app/services.py:760-775`
  - In `_stream_execution_loop`, check if `message_chunk` has `additional_kwargs.get("reasoning_content")`.
  - Emit `{ "type": "reasoning", "text": reasoning_text, "node": node_name }` event via `_emit`.
- Create: `backend/tests/agent/test_sse_reasoning_events.py`
  - Unit tests verifying `ReasoningStreamEvent` model validation and `services.py` SSE reasoning event generation.

---

### Task 1: Extend Schemas with ReasoningStreamEvent

**Files:**
- Modify: `backend/app/schemas.py:130-140`
- Modify: `backend/app/schemas.py:230-245`
- Test: `backend/tests/agent/test_sse_reasoning_events.py`

- [ ] **Step 1: Write the failing test for ReasoningStreamEvent**

```python
# backend/tests/agent/test_sse_reasoning_events.py
import pytest
from backend.app.schemas import ReasoningStreamEvent, ChatStreamEvent, TypeAdapter

def test_reasoning_stream_event_schema():
    event = ReasoningStreamEvent(text="正在分析SQL...", node="agent")
    assert event.type == "reasoning"
    assert event.text == "正在分析SQL..."
    assert event.node == "agent"

def test_chat_stream_event_union_discriminates_reasoning():
    adapter = TypeAdapter(ChatStreamEvent)
    data = {"type": "reasoning", "text": "正在推理...", "node": "agent"}
    parsed = adapter.validate_python(data)
    assert isinstance(parsed, ReasoningStreamEvent)
    assert parsed.text == "正在推理..."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda activate py312_agent; python -m pytest -o pythonpath=. backend/tests/agent/test_sse_reasoning_events.py -v`  
Expected: FAIL with "ImportError: cannot import name 'ReasoningStreamEvent' from 'backend.app.schemas'"

- [ ] **Step 3: Implement ReasoningStreamEvent in schemas.py**

In `backend/app/schemas.py`, add `ReasoningStreamEvent`:

```python
class ReasoningStreamEvent(BaseModel):
    type: Literal["reasoning"] = "reasoning"
    text: str
    node: Optional[str] = None
```

And update `ChatStreamEvent` Union to include `ReasoningStreamEvent`:

```python
ChatStreamEvent = Annotated[
    Union[
        TokenStreamEvent,
        ReasoningStreamEvent,
        StatusStreamEvent,
        ...
    ],
    Field(discriminator="type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda activate py312_agent; python -m pytest -o pythonpath=. backend/tests/agent/test_sse_reasoning_events.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit changes**

```bash
git add backend/app/schemas.py backend/tests/agent/test_sse_reasoning_events.py
git commit -m "feat: add ReasoningStreamEvent to backend schemas"
```

---

### Task 2: Emit Reasoning Stream Events in Services Streaming Loop

**Files:**
- Modify: `backend/app/services.py:760-775`
- Test: `backend/tests/agent/test_sse_reasoning_events.py`

- [ ] **Step 1: Write the failing test for services streaming reasoning extraction**

Add to `backend/tests/agent/test_sse_reasoning_events.py`:

```python
from langchain_core.messages import AIMessageChunk

def test_extract_reasoning_content_from_message_chunk():
    chunk = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "思考：发现表ods.process_areas"})
    reasoning_text = chunk.additional_kwargs.get("reasoning_content")
    assert reasoning_text == "思考：发现表ods.process_areas"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `conda activate py312_agent; python -m pytest -o pythonpath=. backend/tests/agent/test_sse_reasoning_events.py -v`  
Expected: PASS

- [ ] **Step 3: Update `_stream_execution_loop` in `backend/app/services.py`**

In `backend/app/services.py` inside `async for chunk in source_iter:` under `if isinstance(message_chunk, AIMessage):`:

```python
                        if isinstance(message_chunk, AIMessage):
                            # 🚀 优先检测 message_chunk 是否包含思考 Token，若有则推送 stage: reasoning 事件
                            reasoning_text = message_chunk.additional_kwargs.get("reasoning_content")
                            if reasoning_text:
                                await _emit(
                                    {
                                        "type": "reasoning",
                                        "text": reasoning_text,
                                        "node": node_name,
                                    }
                                )

                            for text_segment in self._extract_text_segments(message_chunk):
                                if not text_segment:
                                    continue
                                has_stream_tokens = True
                                await _emit(
                                    {
                                        "type": "token",
                                        "text": text_segment,
                                        "node": node_name,
                                    }
                                )
```

- [ ] **Step 4: Run all agent integration tests**

Run: `conda activate py312_agent; python -m pytest -o pythonpath=. backend/tests/agent/test_chat_deepseek_integration.py backend/tests/agent/test_persistence_integration.py backend/tests/agent/test_sse_reasoning_events.py -v`  
Expected: PASS (All tests passing)

- [ ] **Step 5: Commit changes**

```bash
git add backend/app/services.py backend/tests/agent/test_sse_reasoning_events.py
git commit -m "feat: emit ReasoningStreamEvent in services stream loop"
```
