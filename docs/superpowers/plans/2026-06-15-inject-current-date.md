# Inject Current Date to System Message Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject the real-time local date into the system message dynamically before sending requests to the LLM, enabling the LLM to have accurate time awareness.

**Architecture:** Integrate the date injection logic into the existing `SafeMergeSystemMiddleware` middleware. By intercepting `ModelRequest` before it is dispatched to the LLM, we calculate and append the current date to the end of the `system_message`. This design is non-intrusive (no API/Graph state changes) and prevents time stale issues since the date is computed dynamically on each model invocation.

**Tech Stack:** Python 3.12, LangChain, Pytest

---

### Task 1: Create Unit Tests for Date Injection

**Files:**
- Create: `backend/app/agent/middleware/test_safe_merge_middleware.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
import datetime
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest

from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
from backend.app.agent.state import CustomState

def test_safe_merge_injects_current_date_no_rag():
    state = CustomState(messages=[])
    request = ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    now = datetime.datetime.now()
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')}"
    
    assert expected_date_str in content
    assert "Base system prompt" in content


def test_safe_merge_injects_current_date_with_rag():
    def test_safe_merge_injects_current_date_with_rag():
    rag_msg = SystemMessage(content="This is __business_rag_context__ info")
    state = CustomState(messages=[rag_msg])
    request = ModelRequest(
        model=None,
        messages=[rag_msg],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    now = datetime.datetime.now()
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')}"
    
    assert content.endswith(expected_date_str + "]")
    assert "Base system prompt" in content
    assert "This is __business_rag_context__ info" in content
    assert len(new_request.messages) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n py312_agent pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`
Expected: FAIL (because the middleware doesn't inject date yet, causing assertion error on date string)

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "test: add failing tests for system message date injection"
```

---

### Task 2: Implement Dynamic Date Injection in Middleware

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py:98-156`

- [ ] **Step 1: Write minimal implementation**

Modify the `_modify_request` method in `backend/app/agent/middleware/safe_merge_middleware.py` to calculate and append the date to `system_message`.

```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        # 新增首部调用：动态注入客户端思考模式配置
        self._inject_thinking_config(request)
        
        messages = list(request.messages)
        if not messages:
            return request

        filtered_messages = []
        rag_texts = []

        # 1. 深度遍历全量历史消息队列，定位并抽干所有的 RAG SystemMessage
        for msg in messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                is_rag = False
                
                if isinstance(content, str) and "__business_rag_context__" in content:
                    is_rag = True
                elif hasattr(msg, "content_blocks"):
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_rag = True
                                break

                if is_rag:
                    # 提取该条 RAG 消息的纯文本内容，存入暂存器
                    rag_text = _get_string_content(msg)
                    if rag_text:
                        rag_texts.append(rag_text)
                    # ⚠️ 注意：此处故意不将该消息放入 filtered_messages，以实现彻底的物理抽干！
                    continue

            # 保留其他所有普通消息
            filtered_messages.append(msg)

        # 获取原始 system_message 文本
        sys_text = _get_string_content(request.system_message)

        # 动态获取当前日期和时间并准备注入模板
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"\n\n[系统提示: {date_str}]"

        # 2. 如果检索到了任何 RAG 消息，执行物理合并与对话历史大一统抽干
        if rag_texts:
            logger.info(f"🛡️ SafeMergeSystemMiddleware: 全局打捞检测到 {len(rag_texts)} 条 RAG 消息，正在开启安全自愈合并...")
            
            # 提取全局核心提示词与所有搜集到的 RAG 消息的纯文本
            merged_rag_text = "\n\n".join(rag_texts)
            
            # 用纯文本大一统构筑 SystemMessage，并保证当前日期在整个提示词的最末尾
            merged_content = f"{sys_text}\n\n{merged_rag_text}{date_prompt}"
            new_system_message = SystemMessage(content=merged_content)
            
            logger.info(
                "🛡️ SafeMergeSystemMiddleware: 多 System 消息全量打捞合并完成，"
                "已将所有 RAG 消息规范化为纯文本 SystemMessage 并从 messages 列表中彻底抽干物理抹除！"
            )
            return request.override(
                system_message=new_system_message,
                messages=filtered_messages
            )

        new_system_message = SystemMessage(content=f"{sys_text}{date_prompt}")
        return request.override(
            system_message=new_system_message,
            messages=filtered_messages
        )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `conda run -n py312_agent pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`
Expected: PASS

- [ ] **Step 3: Run all middleware tests to avoid regression**

Run: `conda run -n py312_agent pytest backend/app/agent/middleware/ -v`
Expected: PASS (All tests pass)

- [ ] **Step 4: Commit the implementation**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py
git commit -m "feat: inject current date into system message dynamically in SafeMergeSystemMiddleware"
```
