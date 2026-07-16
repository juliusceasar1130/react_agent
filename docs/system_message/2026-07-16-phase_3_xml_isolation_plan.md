# Phase 3: XML Static/Dynamic Isolation Detailed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement physical zoning of static system rules and dynamic session context inside PromptCompilerMiddleware using XML tags to optimize LLM Prefix Caching.

**Architecture:** Modify PromptCompilerMiddleware's `_modify_request` to parse the `content_blocks` list from `request.system_message`. Segregate blocks into static `<system_rules>` and dynamic `<runtime_context>` sections, wrapping date, active schemas, secondary schemas, and RAG contexts under `<runtime_context>`.

**Tech Stack:** Python 3.12, pytest.

---

### Task 1: Update PromptCompilerMiddleware to compile XML zones

**Files:**
- Modify: `backend/app/agent/middleware/prompt_compiler_middleware.py`

- [ ] **Step 1: Write/adjust the failing test**

We will update the test suite assertions in `backend/app/agent/middleware/test_prompt_compiler_middleware.py` to expect XML tags. Let's modify the first two test cases `test_safe_merge_inject_current_date_no_rag` and `test_safe_merge_inject_current_date_with_rag` as follows:

```python
# backend/app/agent/middleware/test_prompt_compiler_middleware.py

def test_safe_merge_injects_current_date_no_rag():
    state = CustomState(messages=[])
    request = ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
    
    # 验证包含 XML 分区标签
    assert "<system_rules>" in content
    assert "</system_rules>" in content
    assert "<runtime_context>" in content
    assert "</runtime_context>" in content
    
    # 验证静态部分和动态部分在正确的标签分区内
    assert "Base system prompt" in content.split("</system_rules>")[0]
    assert f"[系统提示: {expected_date_str}]" in content.split("<runtime_context>")[1]


def test_safe_merge_injects_current_date_with_rag():
    state = CustomState(
        messages=[],
        lexicon_context={
            "formatted_text": "This is __business_rag_context__ info",
            "tables": []
        }
    )
    request = ModelRequest(
        model=None,
        messages=[],
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
    
    # 验证包含 XML 标签且内容归属正确分区
    assert "<system_rules>" in content
    assert "</system_rules>" in content
    assert "<runtime_context>" in content
    assert "</runtime_context>" in content
    
    assert "Base system prompt" in content.split("</system_rules>")[0]
    assert "This is __business_rag_context__ info" in content.split("<runtime_context>")[1]
    assert f"[系统提示: {expected_date_str}]" in content.split("<runtime_context>")[1]
    assert len(new_request.messages) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run command:
`conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py::test_safe_merge_injects_current_date_no_rag -v`

Expected failure:
`AssertionError: assert '<system_rules>' in 'Base system prompt\n\n[系统提示: 当前日期: ...]'`

- [ ] **Step 3: Write minimal implementation**

Modify `_modify_request` in `backend/app/agent/middleware/prompt_compiler_middleware.py` from line 391 to 450. Replace the entire `_modify_request` method with the following physical XML zoning implementation:

```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """读取 state 中的 RAG 文本直接拼装至系统消息，并清理历史留存的 RAG 污染消息"""
        self._inject_thinking_config(request)
        
        raw_messages = list(request.messages) if request.messages else []
        projected_messages = self._project_and_collapse_messages(raw_messages)

        # 1. 直接从 request.state 中获取结构化 RAG 文本
        lexicon_ctx = request.state.get("lexicon_context") if request.state else {}
        if not lexicon_ctx:
            lexicon_ctx = {}
        rag_text = lexicon_ctx.get("formatted_text", "")

        # 2. 防御性过滤历史数据库中可能残留的老旧 RAG 消息 (向下兼容)
        filtered_messages = []
        for msg in projected_messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                if isinstance(content, str) and "__business_rag_context__" in content:
                    continue
                elif hasattr(msg, "content_blocks"):
                    is_legacy_rag = False
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if "__business_rag_context__" in block.get("text", ""):
                                is_legacy_rag = True
                                break
                    if is_legacy_rag:
                        continue
            filtered_messages.append(msg)

        # 3. 解析 content_blocks 区分静态与动态部分
        blocks = getattr(request.system_message, "content_blocks", None)
        base_sys_text = ""
        skills_addendum = ""
        active_ddl = ""
        secondary_ddl = ""

        if isinstance(blocks, list) and len(blocks) > 0:
            base_sys_text = blocks[0].get("text", "") if isinstance(blocks[0], dict) else str(blocks[0])
            for block in blocks[1:]:
                text = block.get("text", "") if isinstance(block, dict) else str(block)
                if "## Available Skills" in text:
                    skills_addendum = text
                elif "## Active Domain Knowledge" in text:
                    active_ddl = text
                elif "## Secondary Domain Knowledge" in text:
                    secondary_ddl = text
        else:
            base_sys_text = _get_string_content(request.system_message)

        # 4. 组装静态区 (System Rules)
        static_parts = [base_sys_text]
        if skills_addendum:
            static_parts.append(skills_addendum)
        system_rules_content = "\n\n".join(static_parts).strip()
        system_rules_xml = f"<system_rules>\n{system_rules_content}\n</system_rules>"

        # 5. 组装动态区 (Runtime Context)
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"[系统提示: {date_str}]"

        dynamic_parts = [date_prompt]
        if active_ddl:
            dynamic_parts.append(active_ddl.strip())
        if secondary_ddl:
            dynamic_parts.append(secondary_ddl.strip())
        if rag_text:
            dynamic_parts.append(rag_text.strip())
            
        runtime_context_content = "\n\n".join(dynamic_parts).strip()
        runtime_context_xml = f"<runtime_context>\n{runtime_context_content}\n</runtime_context>"

        # 6. 合并编译并重载 ModelRequest
        compiled_content = f"{system_rules_xml}\n\n{runtime_context_xml}"
        new_system_message = SystemMessage(content=compiled_content)
        
        logger.info("🛡️ PromptCompilerMiddleware: 静态/动态双分区编译合并完成。")
        return request.override(
            system_message=new_system_message,
            messages=filtered_messages
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run command:
`conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`

Expected output:
`All 20 tests in backend/app/agent/middleware/test_prompt_compiler_middleware.py passed.`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/prompt_compiler_middleware.py backend/app/agent/middleware/test_prompt_compiler_middleware.py
git commit -m "feat: implement static/dynamic XML prompt zoning for prompt caching"
```

---

## Self-Review

1. **Spec coverage:** The plan covers XML prompt layout structuring, block parser implementation, assertion verification, and backwards compatibility.
2. **Placeholder scan:** Scanned. Fully detailed code replacement and assertions.
3. **Type consistency:** Checked. Field variables `system_rules_xml` and `runtime_context_xml` are consistent.
