# SQL Linter Retry Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement memory-only projection and cleanup for redundant SQL Linter error messages within ReAct loops and across conversation turns to prevent context window overflow.

**Architecture:** We use a text-based header protocol `X-SQL-LINTER-STATUS: FAILED` to tag SQL Linter violations. The custom `SafeMergeSystemMiddleware` will intercept and analyze the message list before any LLM call, redacting older failed attempts while retaining the latest failure context as a correction clue, and collapsing all past attempts once query success is reached.

**Tech Stack:** Python 3.12, LangChain Core, LangGraph, pytest.

---

### Task 1: Add Linter Failure Protocol Header

**Files:**
- Modify: `backend/app/agent/utils/sql_linter.py`
- Modify: `backend/app/agent/tools/sql_tools.py`
- Test: `backend/app/agent/utils/test_sql_linter_header.py` (New Test File)

- [ ] **Step 1: Write the test verifying the header protocol is added**

Create `backend/app/agent/utils/test_sql_linter_header.py`:
```python
import pytest
from backend.app.agent.utils.sql_linter import LintResult, LintViolation

def test_lint_result_error_formatting_includes_header():
    violation = LintViolation(
        rule_id="SEM-001",
        severity="ERROR",
        message="JOIN columns are not unique.",
        detail="JOIN ON t0.a = t1.a",
        fix_suggestion="Use GROUP BY"
    )
    result = LintResult(passed=False, errors=[violation], warnings=[])
    formatted = result.format_error_message()
    
    # Assert header exists at the top
    assert formatted.startswith("X-SQL-LINTER-STATUS: FAILED")
    assert "Error: SQL Linter 拦截 — 检测到以下问题：" in formatted
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest backend/app/agent/utils/test_sql_linter_header.py -v`
Expected: FAIL due to missing header in output or test file not run because implementation does not output it.

- [ ] **Step 3: Modify format_error_message to include header**

Modify `backend/app/agent/utils/sql_linter.py` (around line 63):
```python
    def format_error_message(self) -> str:
        lines = [
            "X-SQL-LINTER-STATUS: FAILED",
            "Error: SQL Linter 拦截 — 检测到以下问题：\n"
        ]
        for i, error in enumerate(self.errors, 1):
            lines.append(f"{i}. [{error.severity}] {error.rule_id}: {error.message}")
            if error.detail:
                lines.append(f"   检测到: {error.detail}")
            if error.fix_suggestion:
                lines.append(f"   修复建议: {error.fix_suggestion}\n")
        lines.append("请修正 SQL 后重试。")
        return "\n".join(lines)
```

Also, modify `backend/app/agent/tools/sql_tools.py` (around line 248) inside the `sqlglot` parse exception handling:
```python
                errors = [v for v in raw_violations if v.severity == "ERROR"]
                if errors:
                    dummy_result = LintResult(passed=False, errors=errors, warnings=[])
                    err_msg = dummy_result.format_error_message()
                    logger.warning(f"Linter 校验拦截 (退避模式):\n{err_msg}")
                    raise ToolException(err_msg)
```
*(No code modification needed here since it delegates formatting to `dummy_result.format_error_message()`, which already prepends the header. We just verify the logic matches).*

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest backend/app/agent/utils/test_sql_linter_header.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/utils/sql_linter.py backend/app/agent/utils/test_sql_linter_header.py
git commit -m "feat(linter): prepend X-SQL-LINTER-STATUS: FAILED to formatted errors"
```

---

### Task 2: Implement Redaction Logic in SafeMergeSystemMiddleware

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`
- Modify: `backend/app/agent/middleware/test_safe_merge_middleware.py`

- [ ] **Step 1: Write tests for multiple failures redaction**

Modify `backend/app/agent/middleware/test_safe_merge_middleware.py` to append the following tests:
```python
def test_safe_merge_redacts_past_failures_keeps_latest():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain.agents.middleware.types import ModelRequest
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
    
    messages = [
        HumanMessage(content="Query active users"),
        # Attempt 1: Failed (Should be redacted)
        AIMessage(content="Trying SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),
        
        # Attempt 2: Failed (Should be redacted)
        AIMessage(content="Trying SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_2"),
        
        # Attempt 3: Failed (Latest, should be KEPT as clue)
        AIMessage(content="Trying SQL 3", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 3"}, "id": "call_3"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SYN-002", name="sql_db_query", tool_call_id="call_3"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    # Assertions:
    # 1. Attempt 1 & 2 are redacted
    assert new_request.messages[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[1].tool_calls[0]["args"]["query"] == "-- redacted --"
    assert new_request.messages[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    assert new_request.messages[3].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[4].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # 2. Attempt 3 (Latest failure) is preserved untouched
    assert new_request.messages[5].content == "Trying SQL 3"
    assert new_request.messages[6].content == "X-SQL-LINTER-STATUS: FAILED\nError: SYN-002"


def test_safe_merge_redacts_all_failures_on_success():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain.agents.middleware.types import ModelRequest
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
    
    messages = [
        HumanMessage(content="Query active users"),
        # Attempt 1: Failed (Should be redacted)
        AIMessage(content="Trying SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),
        
        # Attempt 2: Successful (Should be preserved)
        AIMessage(content="Trying SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="call_2"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    # Assertions:
    # 1. Attempt 1 is redacted
    assert new_request.messages[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # 2. Attempt 2 (Success) is kept untouched (sliding window is latest, so not collapsed)
    assert new_request.messages[3].content == "Trying SQL 2"
    assert new_request.messages[4].content == "[{'id': 1}]"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`
Expected: FAIL due to missing redaction logic.

- [ ] **Step 3: Modify SafeMergeSystemMiddleware code**

Replace `_project_and_collapse_messages` in `backend/app/agent/middleware/safe_merge_middleware.py` (lines 80-145) with:
```python
    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        if not messages:
            return []

        # 1. Perform a shallow copy of messages to protect State messages
        projected = [msg for msg in messages]

        # 2. Count HumanMessages from the end to find the sliding window boundary
        protect_turns = settings.llm_context_collapse_protect_turns
        boundary_index = 0
        human_count = 0
        for idx in range(len(projected) - 1, -1, -1):
            if isinstance(projected[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    boundary_index = idx
                    break

        # 3. Pre-scan: collect metadata for sql_db_query tools
        sql_tool_infos = []
        for idx, msg in enumerate(projected):
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                sql_tool_infos.append({
                    "idx": idx,
                    "tool_call_id": msg.tool_call_id,
                    "is_linter_error": is_linter_error,
                })

        # 4. Find successful and latest failed call_ids
        successful_sql_call_id = None
        for info in reversed(sql_tool_infos):
            if not info["is_linter_error"]:
                successful_sql_call_id = info["tool_call_id"]
                break

        latest_failed_sql_call_id = None
        if successful_sql_call_id is None:
            for info in reversed(sql_tool_infos):
                if info["is_linter_error"]:
                    latest_failed_sql_call_id = info["tool_call_id"]
                    break

        # 5. Build kept call IDs
        kept_call_ids = set()
        if latest_failed_sql_call_id:
            kept_call_ids.add(latest_failed_sql_call_id)
        if successful_sql_call_id:
            kept_call_ids.add(successful_sql_call_id)

        # 6. Apply redaction and collapse
        redacted_count = 0
        kept_count = 0

        for idx in range(len(projected)):
            msg = projected[idx]
            
            # ── SQL Linter failure redaction (Time 1 & 2) ──
            if isinstance(msg, ToolMessage) and msg.name == "sql_db_query":
                content_str = str(msg.content)
                is_linter_error = (
                    "X-SQL-LINTER-STATUS: FAILED" in content_str or
                    ("Linter 拦截" in content_str or "SQL Linter" in content_str)
                )
                
                if is_linter_error:
                    should_redact = (
                        (successful_sql_call_id is not None) or
                        (latest_failed_sql_call_id is not None and msg.tool_call_id != latest_failed_sql_call_id)
                    )
                    
                    if should_redact:
                        redacted_count += 1
                        projected[idx] = ToolMessage(
                            content="[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                        for back_idx in range(idx - 1, -1, -1):
                            aimsg = projected[back_idx]
                            if isinstance(aimsg, AIMessage) and hasattr(aimsg, "tool_calls"):
                                if any(tc.get("id") == msg.tool_call_id for tc in aimsg.tool_calls):
                                    projected[back_idx] = AIMessage(
                                        content="[Invalid SQL attempt. Redacted to save context space.]",
                                        tool_calls=[{
                                            "name": "sql_db_query",
                                            "args": {"query": "-- redacted --"},
                                            "id": msg.tool_call_id,
                                            "type": "tool_call"
                                        }]
                                    )
                                    break
                        continue
                    else:
                        kept_count += 1

            # ── Standard Collapsible Tools logic outside sliding window ──
            if isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS:
                if msg.tool_call_id in kept_call_ids:
                    continue
                if idx < boundary_index:
                    if msg.name == "sql_db_query":
                        content_str = str(msg.content)
                        is_err = "Error" in content_str or "exception" in content_str.lower()
                        if is_err:
                            projected[idx] = ToolMessage(
                                content="[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]",
                                name=msg.name,
                                tool_call_id=msg.tool_call_id
                            )
                        else:
                            projected[idx] = ToolMessage(
                                content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                                name=msg.name,
                                tool_call_id=msg.tool_call_id
                            )
                    elif msg.name == "search_saved_correct_tool_uses":
                        projected[idx] = ToolMessage(
                            content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    elif msg.name == "build_chart_artifact":
                        projected[idx] = ToolMessage(
                            content="[Chart generated successfully. ECharts JSON config collapsed.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    elif msg.name in ("export_to_csv", "export_query_to_csv"):
                        projected[idx] = ToolMessage(
                            content="[CSV export completed and collapsed. User has already received the download link.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )

        if redacted_count > 0 or kept_count > 0:
            logger.info(
                "🛡️ SQL Linter Redaction: %d failures redacted, %d kept as correction clue. "
                "Kept call_ids: %s",
                redacted_count, kept_count, kept_call_ids
            )

        return projected
```

- [ ] **Step 4: Run all safe merge middleware tests**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`
Expected: PASS (Both existing and new tests should pass).

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(middleware): implement linter retry redaction and keep clues"
```

---

### Task 3: Verify the Integrated System

- [ ] **Step 1: Run complete test suite**

Run: `pytest -v` (within `backend` or via terminal)
Expected: All tests pass.

- [ ] **Step 2: Commit final verification**

```bash
git status
# Ensure clean workspace except the changes made
```
