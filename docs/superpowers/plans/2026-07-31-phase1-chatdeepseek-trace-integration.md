# Phase 1: ChatDeepSeek Model Switch & Trace Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `ChatOpenAI` with `ChatDeepSeek` in `backend/app/agent/service.py` to extract `reasoning_content` from vLLM Qwen 3.6 responses into `AIMessage.additional_kwargs`, enabling LangSmith Trace observablity.

**Architecture:** Switch LLM instantiation in `_create_llm` to `ChatDeepSeek` (`langchain-deepseek==1.0.1`), map API keys/base URL arguments, update test patches, and verify reasoning content populates in `AIMessage.additional_kwargs["reasoning_content"]`.

**Tech Stack:** Python 3.12, LangChain, `langchain-deepseek 1.0.1`, pytest, vLLM, LangSmith.

---

## File Structure & Responsibilities

- `backend/app/agent/service.py`: LLM factory function `_create_llm` and `SQLAgentService` initialization. Responsible for instantiating `ChatDeepSeek` with correct parameter mapping (`api_key`, `api_base`, `extra_body`).
- `backend/tests/agent/test_persistence_integration.py`: Unit and integration test for agent persistence. Must patch `ChatDeepSeek` instead of `ChatOpenAI`.
- `backend/tests/agent/test_chat_deepseek_integration.py`: New unit test to verify that `ChatDeepSeek` properly initializes with `api_key`/`api_base` and maps `reasoning_content` to `AIMessage.additional_kwargs`.

---

### Task 1: Add Unit Test for ChatDeepSeek Initialization and Reasoning Content Mapping

**Files:**
- Create: `backend/tests/agent/test_chat_deepseek_integration.py`

- [ ] **Step 1: Write the unit test**

```python
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek
from backend.app.agent.service import _create_llm

def test_create_llm_instantiates_chat_deepseek(monkeypatch):
    """验证 _create_llm 在使用默认/DeepSeek模式时可正确实例化 ChatDeepSeek"""
    with patch("backend.app.agent.service.ChatDeepSeek") as mock_chat_deepseek:
        mock_instance = MagicMock()
        mock_chat_deepseek.return_value = mock_instance
        
        llm = _create_llm(use_ollama=False)
        
        assert llm == mock_instance
        mock_chat_deepseek.assert_called_once()
        call_kwargs = mock_chat_deepseek.call_args.kwargs
        assert "api_key" in call_kwargs
        assert "api_base" in call_kwargs
        assert "openai_api_key" not in call_kwargs
        assert "openai_api_base" not in call_kwargs

def test_chat_deepseek_reasoning_content_mapping():
    """验证 ChatDeepSeek 反序列化时保留 reasoning_content"""
    llm = ChatDeepSeek(
        model="gpt-5-nano",
        api_base="http://localhost:8089/v1",
        api_key="EMPTY",
    )
    
    mock_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 123456789,
        "model": "gpt-5-nano",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "744 台正常车",
                    "reasoning_content": "正在分析车间各区域车辆分布...",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    
    result = llm._create_chat_result(mock_response)
    message = result.generations[0].message
    assert isinstance(message, AIMessage)
    assert message.content == "744 台正常车"
    assert message.additional_kwargs.get("reasoning_content") == "正在分析车间各区域车辆分布..."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/agent/test_chat_deepseek_integration.py -v`
Expected: FAIL with `AssertionError` or `ImportError` because `_create_llm` in `service.py` still calls `ChatOpenAI`.

---

### Task 2: Update `_create_llm` in `service.py` to Use `ChatDeepSeek`

**Files:**
- Modify: `backend/app/agent/service.py:32`
- Modify: `backend/app/agent/service.py:150-187`

- [ ] **Step 1: Update imports in `backend/app/agent/service.py`**

Replace `from langchain_openai import ChatOpenAI` with `from langchain_deepseek import ChatDeepSeek`.

- [ ] **Step 2: Update `_create_llm` function in `backend/app/agent/service.py`**

```python
    # 1. 组装标准参数
    kwargs: dict[str, Any] = {
        "model": settings.deepseek_model,
        "temperature": settings.agent_temperature,
        "api_key": settings.deepseek_api_key or "EMPTY",
        "api_base": settings.deepseek_base_url,
        "max_tokens": settings.agent_max_tokens,
        "request_timeout": settings.llm_timeout,
        "max_retries": settings.llm_max_retries,
    }

    # top_p 和 presence_penalty 属于 OpenAI 官方一级标准参数，直接在顶层参数传递以防触发 UserWarning
    if settings.llm_top_p is not None:
        kwargs["top_p"] = settings.llm_top_p
    if settings.llm_presence_penalty is not None:
        kwargs["presence_penalty"] = settings.llm_presence_penalty

    # 2. 动态检测并将 vLLM 特有的非标准采样参数安全包裹在 extra_body 中透传，规避 OpenAI SDK 的参数强拦截
    extra_body: dict[str, Any] = {}
    if settings.llm_top_k is not None:
        extra_body["top_k"] = settings.llm_top_k
    if settings.llm_repetition_penalty is not None:
        extra_body["repetition_penalty"] = settings.llm_repetition_penalty
    if settings.llm_min_p is not None:
        extra_body["min_p"] = settings.llm_min_p
    if settings.llm_enable_thinking is not None:
        extra_body["chat_template_kwargs"] = {
            "enable_thinking": settings.llm_enable_thinking
        }

    if extra_body:
        kwargs["extra_body"] = extra_body

    logger.info(
        "Initializing ChatDeepSeek with arguments: %s",
        {k: v for k, v in kwargs.items() if k != "api_key"},
    )
    return ChatDeepSeek(**kwargs)
```

- [ ] **Step 3: Run new unit test to verify it passes**

Run: `pytest backend/tests/agent/test_chat_deepseek_integration.py -v`
Expected: PASS

---

### Task 3: Update Existing Test Patching in `test_persistence_integration.py`

**Files:**
- Modify: `backend/tests/agent/test_persistence_integration.py:8`
- Modify: `backend/tests/agent/test_persistence_integration.py:31`
- Modify: `backend/tests/agent/test_persistence_integration.py:41`

- [ ] **Step 1: Update `test_persistence_integration.py` to patch `ChatDeepSeek`**

Replace:
```python
from langchain_openai import ChatOpenAI
...
    mock_llm = MagicMock(spec=ChatOpenAI)
...
    patch("backend.app.agent.service.ChatOpenAI", return_value=mock_llm),
```
With:
```python
from langchain_deepseek import ChatDeepSeek
...
    mock_llm = MagicMock(spec=ChatDeepSeek)
...
    patch("backend.app.agent.service.ChatDeepSeek", return_value=mock_llm),
```

- [ ] **Step 2: Run all agent backend tests to verify clean pass**

Run: `pytest backend/tests/agent/ -v`
Expected: PASS all tests.

---

### Task 4: End-to-End Verification Checklist

- [ ] **Step 1: Check `.env` setting `LLM_ENABLE_THINKING`**
Ensure `.env` sets `LLM_ENABLE_THINKING=true`.

- [ ] **Step 2: Verification Run**
Verify backend initializes with `ChatDeepSeek` and `AIMessage.additional_kwargs["reasoning_content"]` is captured into LangSmith Trace.
