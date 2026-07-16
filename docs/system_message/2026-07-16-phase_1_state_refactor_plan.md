# Phase 1: State Refactoring & RAG Decoupling Detailed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the RAG context transmission from history message mutation to structured state fields, eliminating database pollution.

**Architecture:** BusinessRagMiddleware's `before_model` and `abefore_model` hooks will stop returning message list updates and will instead populate state dictionary keys `rag_context` and `lexicon_context`. SafeMergeSystemMiddleware will then read these context keys directly from `request.state` and merge them into the final compiled SystemMessage, while maintaining message collapsing and correction linter history.

**Tech Stack:** Python 3.12, FastAPI, LangChain, LangGraph, pytest.

---

### Task 1: Refactor BusinessRagMiddleware state update

**Files:**
- Modify: `backend/app/agent/middleware/rag_middleware.py`
- Test: `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py`

- [ ] **Step 1: Write the failing test**

Modify the test `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py` as follows:

```python
# backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py
# Modify the assertions at the end of test_business_rag_middleware_abefore_model:

        # Call abefore_model
        state = {"messages": [HumanMessage(content="查询测试")]}
        runtime = MagicMock()
        
        result = await middleware.abefore_model(state, runtime)
        assert result is not None
        
        # 1. 验证返回值中不再包含 "messages" (不再向历史塞入消息)
        assert "messages" not in result
        
        # 2. 验证格式化好的 RAG 文本直接保存在 lexicon_context 状态中
        assert "lexicon_context" in result
        assert "formatted_text" in result["lexicon_context"]
        assert "CREATE TABLE dim_test_table" in result["lexicon_context"]["formatted_text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run command:
`conda activate py312_agent; pytest backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py -v`

Expected failure:
`AssertionError: assert 'messages' not in {'messages': ..., 'rag_context': ..., 'rag_query': ..., 'lexicon_context': ...}`

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/agent/middleware/rag_middleware.py` from line 410 to 461. Replace the entire code block that builds and inserts the `rag_system_message` into `new_messages` with the following clean dictionary state update:

```python
        # Remove lines 410-444 (draining/inserting code block) and modify the return dictionary:
        
        logger.info("BusinessRagMiddleware: 已将混合辅助知识注入到 state 的 lexicon_context")
        emit_stream_status(
            f"辅助知识与物理词典装配完毕 (DDL 并集共 {len(table_lexicon_context)} 张表)",
            stage="retrieving",
            source="business_rag",
        )

        return {
            "rag_context": retrieved_docs,
            "rag_query": user_query,
            "lexicon_context": {
                "formatted_text": rag_system_content,
                "tables": table_lexicon_context,
                "values_count": len(lexicon_results.get("values", [])),
                "rows_count": len(lexicon_results.get("rows", []))
            }
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run command:
`conda activate py312_agent; pytest backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py -v`

Expected output:
`PASSED backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py::test_business_rag_middleware_abefore_model`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/rag_middleware.py backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py
git commit -m "refactor: decouple RAG middleware from messages list"
```

---

### Task 2: Refactor SafeMergeSystemMiddleware prompt assembly

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`
- Test: `backend/app/agent/middleware/test_safe_merge_middleware.py`

- [ ] **Step 1: Write the failing test**

Modify `test_safe_merge_inject_current_date_with_rag` in `backend/app/agent/middleware/test_safe_merge_middleware.py` to populate state variables instead of the message list:

```python
# backend/app/agent/middleware/test_safe_merge_middleware.py
# Modify test_safe_merge_inject_current_date_with_rag:

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
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    content = str(new_request.system_message.content)
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
    
    assert f"[系统提示: {expected_date_str}]" in content
    assert content.endswith(f"[系统提示: {expected_date_str}]")
    assert "Base system prompt" in content
    assert "This is __business_rag_context__ info" in content
    assert len(new_request.messages) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run command:
`conda activate py312_agent; pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_safe_merge_injects_current_date_with_rag -v`

Expected failure:
`AssertionError: assert 'This is __business_rag_context__ info' in ... (since RAG text is not merged because the old code scans messages, not state)`

- [ ] **Step 3: Write minimal implementation**

Modify `_modify_request` in `backend/app/agent/middleware/safe_merge_middleware.py` from line 395 to 462. Replace the old message-scanning and merging code block with:

```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        """读取 state 中的 RAG 文本直接拼装至系统消息，并清理历史留存的 RAG 污染消息"""
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

        # 获取原始 system_message 文本
        sys_text = _get_string_content(request.system_message)

        # 动态获取当前日期和时间并准备注入模板
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"\n\n[系统提示: {date_str}]"

        # 3. 物理合并并重载 ModelRequest
        if rag_text:
            merged_content = f"{sys_text}\n\n{rag_text}{date_prompt}"
            new_system_message = SystemMessage(content=merged_content)
            logger.info("🛡️ SafeMergeSystemMiddleware: 状态化 RAG 消息合并完成。")
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

- [ ] **Step 4: Run test to verify it passes**

Run command:
`conda activate py312_agent; pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`

Expected output:
`All tests in backend/app/agent/middleware/test_safe_merge_middleware.py passed.`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "refactor: safe merge middleware reads RAG text directly from state"
```

---

## Self-Review

1. **Spec coverage:** The plan targets all Phase 1 specifications defined in `phase_1_state_refactor_spec.md`, including `BusinessRagMiddleware` state return mutations, `SafeMergeSystemMiddleware` direct state reads, defensive legacy RAG message filtering, and test case adaptations.
2. **Placeholder scan:** Scanned. All code blocks contain complete implementation code. All pytest commands are exact.
3. **Type consistency:** Checked. Field names `formatted_text` and `lexicon_context` are consistent with state definitions.
