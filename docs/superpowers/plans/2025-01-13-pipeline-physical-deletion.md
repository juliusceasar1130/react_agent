# Pipeline Physical Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `_project_and_collapse_messages` into a 5-stage lightweight Pipeline with paired physical deletion for failed tool calls outside the sliding window.

**Architecture:** Split monolithic `_project_and_collapse_messages` (140 lines) into discrete `_stage_*` private methods sharing a `_CollapseContext` dataclass. Physical deletion intercepts failed `sql_db_query` and `build_chart_artifact` pairs before standard collapse.

**Tech Stack:** Python 3.12, pytest, langchain-core

---

## File Structure

| File | Responsibility | Change |
|------|---------------|--------|
| `backend/app/agent/middleware/safe_merge_middleware.py` | Pipeline stages + context + main entry | Modify (refactor) |
| `backend/app/agent/middleware/test_safe_merge_middleware.py` | Unit tests for all 5 stages | Modify (append) |

---

## Task 1: Create `_CollapseContext` Dataclass

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py:9-19` (imports + logger)

- [ ] **Step 1: Add dataclass import and define `_CollapseContext`**

```python
from dataclasses import dataclass, field
# ... existing imports ...

@dataclass
class _CollapseContext:
    """Pipeline shared context for boundary, deletion, and collapse tracking."""
    messages: list[Any]
    boundary_index: int = 0
    deleted_call_ids: set[str] = field(default_factory=set)
    kept_call_ids: set[str] = field(default_factory=set)
    redacted_count: int = 0
    kept_count: int = 0
    deleted_count: int = 0
```

- [ ] **Step 2: Verify import compiles**

Run: `python -c "from backend.app.agent.middleware.safe_merge_middleware import _CollapseContext; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py
git commit -m "feat(collapse): add _CollapseContext dataclass for pipeline context"
```

---

## Task 2: Extract `_stage_compute_boundary`

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py:80-96` (existing boundary logic)

- [ ] **Step 1: Write the failing test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_stage_compute_boundary_protects_last_n_human_messages():
    from langchain_core.messages import HumanMessage, AIMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
    
    messages = [
        HumanMessage(content="H1"),
        AIMessage(content="A1"),
        HumanMessage(content="H2"),
        AIMessage(content="A2"),
        HumanMessage(content="H3"),
        AIMessage(content="A3"),
        HumanMessage(content="H4"),
        AIMessage(content="A4"),
        HumanMessage(content="H5"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    # Assume protect_turns = 3 from settings
    # H5 is last, H4 is second-to-last, H3 is third-to-last
    # boundary_index should point to H3 (index 4 if 0-indexed)
    boundary = middleware._stage_compute_boundary(messages)
    # The third HumanMessage from the end is at index 4 (H3)
    assert boundary == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_compute_boundary_protects_last_n_human_messages -v`
Expected: `FAIL` with `AttributeError: 'SafeMergeSystemMiddleware' object has no attribute '_stage_compute_boundary'`

- [ ] **Step 3: Extract `_stage_compute_boundary` method**

In `SafeMergeSystemMiddleware`, replace the inline boundary logic (lines 87-96) with:

```python
    def _stage_compute_boundary(self, messages: list[Any]) -> int:
        """Stage 1: Compute sliding window boundary from the end."""
        protect_turns = settings.llm_context_collapse_protect_turns
        human_count = 0
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                human_count += 1
                if human_count == protect_turns:
                    return idx
        return 0
```

Update `_project_and_collapse_messages` to call it:
```python
        # Stage 1: Compute sliding window boundary
        boundary_index = self._stage_compute_boundary(messages)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_compute_boundary_protects_last_n_human_messages -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(collapse): extract _stage_compute_boundary from monolith"
```

---

## Task 3: Extract `_stage_prescan_failures` (Physical Deletion Target Scan)

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write the failing test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_stage_prescan_sql_linter_failure():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_fail"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    middleware._stage_prescan_failures(ctx)
    
    assert "call_fail" in ctx.deleted_call_ids


def test_stage_prescan_chart_runtime_failure():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Chart"),
        ToolMessage(content="X-CHART-STATUS: FAILED\nError: bad json", name="build_chart_artifact", tool_call_id="call_chart"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    middleware._stage_prescan_failures(ctx)
    
    assert "call_chart" in ctx.deleted_call_ids


def test_stage_prescan_success_not_deleted():
    """Successful SQL query should NOT be marked for deletion."""
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="[{'id': 1, 'name': 'Alice'}]", name="sql_db_query", tool_call_id="call_ok"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    middleware._stage_prescan_failures(ctx)
    
    assert "call_ok" not in ctx.deleted_call_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_sql_linter_failure backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_chart_runtime_failure backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_success_not_deleted -v`
Expected: All `FAIL` with `AttributeError`

- [ ] **Step 3: Add `_DELETION_TARGET_CONFIG` and `_stage_prescan_failures`**

In `SafeMergeSystemMiddleware`, add class-level config and method:

```python
    _DELETION_TARGET_CONFIG = {
        "sql_db_query": {
            "has_linter": True,
            "has_runtime": True,
            "runtime_header": "X-SQL-EXECUTION-STATUS: FAILED",
        },
        "build_chart_artifact": {
            "has_linter": False,
            "has_runtime": True,
            "runtime_header": "X-CHART-STATUS: FAILED",
        },
    }

    def _stage_prescan_failures(self, ctx: _CollapseContext) -> None:
        """Stage 2: Pre-scan window-out messages for failed tool calls."""
        for idx in range(ctx.boundary_index):
            msg = ctx.messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in self._DELETION_TARGET_CONFIG:
                continue

            config = self._DELETION_TARGET_CONFIG[msg.name]
            content_str = str(msg.content)
            is_failed = False

            if config["has_linter"] and "X-SQL-LINTER-STATUS: FAILED" in content_str:
                is_failed = True
            elif config["has_runtime"] and config["runtime_header"] in content_str:
                is_failed = True
            else:
                # Fallback: JSON success detection + keyword matching
                is_json_success = False
                try:
                    import json
                    data = json.loads(content_str)
                    if isinstance(data, list):
                        is_json_success = True
                except Exception:
                    pass
                
                if not is_json_success:
                    is_failed = (
                        "error" in content_str.lower() or 
                        "exception" in content_str.lower() or
                        "failed" in content_str.lower()
                    )

            if is_failed:
                ctx.deleted_call_ids.add(msg.tool_call_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_sql_linter_failure backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_chart_runtime_failure backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_prescan_success_not_deleted -v`
Expected: All `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(collapse): add _stage_prescan_failures for physical deletion targets"
```

---

## Task 4: Extract `_stage_redaction`

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write the failing test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_stage_redaction_keeps_latest_failure():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Query"),
        AIMessage(content="SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),
        
        AIMessage(content="SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-002", name="sql_db_query", tool_call_id="call_2"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)
    
    # Latest failure (call_2) should be kept
    assert result[4].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-002"
    assert result[3].content == "SQL 2"
    
    # Earlier failure (call_1) should be redacted
    assert result[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    assert result[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_redaction_keeps_latest_failure -v`
Expected: `FAIL` with `AttributeError`

- [ ] **Step 3: Extract `_stage_redaction` method**

Move the existing redaction logic (lines 99-173 in the original) into `_stage_redaction`:

```python
    def _stage_redaction(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 3: Redact past Linter failures, keeping only the latest as a correction clue."""
        projected = list(messages)

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

        ctx.kept_call_ids = set()
        if latest_failed_sql_call_id:
            ctx.kept_call_ids.add(latest_failed_sql_call_id)

        for idx in range(len(projected)):
            msg = projected[idx]
            if not (isinstance(msg, ToolMessage) and msg.name == "sql_db_query"):
                continue

            content_str = str(msg.content)
            is_linter_error = (
                "X-SQL-LINTER-STATUS: FAILED" in content_str or
                ("Linter 拦截" in content_str or "SQL Linter" in content_str)
            )

            if is_linter_error:
                should_redact = (
                    (successful_sql_call_id is not None) or
                    (latest_failed_sql_call_id is not None and
                     msg.tool_call_id != latest_failed_sql_call_id)
                )
                if should_redact:
                    ctx.redacted_count += 1
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
                                    tool_calls=aimsg.tool_calls
                                )
                                break
                else:
                    ctx.kept_count += 1

        return projected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_redaction_keeps_latest_failure -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(collapse): extract _stage_redaction for Linter failure handling"
```

---

## Task 5: Extract `_stage_physical_deletion`

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write the failing test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_stage_physical_deletion_removes_failed_pairs():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Query"),
        AIMessage(content="SQL fail", tool_calls=[{"name": "sql_db_query", "args": {"query": "bad"}, "id": "call_fail"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED", name="sql_db_query", tool_call_id="call_fail"),
        
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=3, deleted_call_ids={"call_fail"})
    result = middleware._stage_physical_deletion(messages, ctx)
    
    # Both AIMessage and ToolMessage for call_fail should be removed
    assert len(result) == 4  # H1, H2, H3, H4 (M1, M2, M3 plus original H1)
    assert all(not (isinstance(m, ToolMessage) and m.tool_call_id == "call_fail") for m in result)


def test_stage_physical_deletion_partial_filter_keeps_ai_message():
    """If AIMessage has multiple tool_calls and only one fails, keep the AIMessage."""
    from langchain_core.messages import AIMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        AIMessage(content="Multi call", tool_calls=[
            {"name": "sql_db_query", "args": {"query": "bad"}, "id": "call_fail"},
            {"name": "search_saved_correct_tool_uses", "args": {}, "id": "call_ok"}
        ]),
        ToolMessage(content="Error", name="sql_db_query", tool_call_id="call_fail"),
        ToolMessage(content="OK", name="search_saved_correct_tool_uses", tool_call_id="call_ok"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0, deleted_call_ids={"call_fail"})
    result = middleware._stage_physical_deletion(messages, ctx)
    
    # AIMessage should be kept with only the successful tool_call
    assert len(result) == 2
    assert isinstance(result[0], AIMessage)
    assert len(result[0].tool_calls) == 1
    assert result[0].tool_calls[0]["id"] == "call_ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_physical_deletion_removes_failed_pairs backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_physical_deletion_partial_filter_keeps_ai_message -v`
Expected: Both `FAIL` with `AttributeError`

- [ ] **Step 3: Implement `_stage_physical_deletion`**

```python
    def _stage_physical_deletion(self, projected: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 4: Physically delete failed tool call pairs (AIMessage + ToolMessage)."""
        if not ctx.deleted_call_ids:
            return projected

        filtered = []
        for msg in projected:
            if isinstance(msg, ToolMessage) and msg.tool_call_id in ctx.deleted_call_ids:
                ctx.deleted_count += 1
                continue

            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                remaining_tool_calls = []
                for tc in msg.tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id not in ctx.deleted_call_ids:
                        remaining_tool_calls.append(tc)

                is_system_placeholder = (
                    not msg.content or
                    (isinstance(msg.content, str) and msg.content.strip().startswith("["))
                )
                if not remaining_tool_calls and is_system_placeholder:
                    ctx.deleted_count += 1
                    continue

                if len(remaining_tool_calls) != len(msg.tool_calls):
                    msg = AIMessage(
                        content=msg.content,
                        tool_calls=remaining_tool_calls,
                        id=getattr(msg, "id", None)
                    )

            filtered.append(msg)

        return filtered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_physical_deletion_removes_failed_pairs backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_physical_deletion_partial_filter_keeps_ai_message -v`
Expected: Both `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(collapse): add _stage_physical_deletion for failed pair removal"
```

---

## Task 6: Extract `_stage_standard_collapse`

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write the failing test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_stage_standard_collapse_sql_success():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="call_ok"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    result = middleware._stage_standard_collapse(messages, ctx)
    
    assert result[1].content == "[SQL execution successful. Result content collapsed. Re-run query if details are needed.]"


def test_stage_standard_collapse_chart_success():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware, _CollapseContext
    
    messages = [
        HumanMessage(content="Chart"),
        ToolMessage(content="{\"data\": []}", name="build_chart_artifact", tool_call_id="call_chart"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    result = middleware._stage_standard_collapse(messages, ctx)
    
    assert result[1].content == "[Chart generated successfully. ECharts JSON config collapsed.]"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_standard_collapse_sql_success backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_standard_collapse_chart_success -v`
Expected: Both `FAIL`

- [ ] **Step 3: Implement `_stage_standard_collapse`**

```python
    def _stage_standard_collapse(self, messages: list[Any], ctx: _CollapseContext) -> list[Any]:
        """Stage 5: Collapse remaining COLLAPSIBLE_TOOLS outside the sliding window."""
        for idx in range(len(messages)):
            msg = messages[idx]
            if not (isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS):
                continue
            if msg.tool_call_id in ctx.kept_call_ids:
                continue
            if idx >= ctx.boundary_index:
                continue

            if msg.name == "sql_db_query":
                messages[idx] = ToolMessage(
                    content="[SQL execution successful. Result content collapsed. Re-run query if details are needed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "search_saved_correct_tool_uses":
                messages[idx] = ToolMessage(
                    content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name == "build_chart_artifact":
                messages[idx] = ToolMessage(
                    content="[Chart generated successfully. ECharts JSON config collapsed.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )
            elif msg.name in ("export_to_csv", "export_query_to_csv"):
                messages[idx] = ToolMessage(
                    content="[CSV export completed and collapsed. User has already received the download link.]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                )

        return messages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_standard_collapse_sql_success backend/app/agent/middleware/test_safe_merge_middleware.py::test_stage_standard_collapse_chart_success -v`
Expected: Both `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "feat(collapse): add _stage_standard_collapse for remaining tools"
```

---

## Task 7: Wire Pipeline Together in `_project_and_collapse_messages`

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write the failing integration test**

In `backend/app/agent/middleware/test_safe_merge_middleware.py`, append:

```python
def test_pipeline_integration_physical_deletion_before_collapse():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
    
    messages = [
        HumanMessage(content="Query 1"),
        AIMessage(content="SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "bad"}, "id": "call_fail"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_fail"),
        
        HumanMessage(content="Query 2"),
        AIMessage(content="SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "good"}, "id": "call_ok"}]),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="call_ok"),
        
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    middleware = SafeMergeSystemMiddleware()
    result = middleware._project_and_collapse_messages(messages)
    
    # call_fail pair should be physically deleted
    assert all(not (isinstance(m, ToolMessage) and m.tool_call_id == "call_fail") for m in result)
    
    # call_ok should be collapsed (not deleted, but content replaced)
    ok_msg = next(m for m in result if isinstance(m, ToolMessage) and m.tool_call_id == "call_ok")
    assert "collapsed" in ok_msg.content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_pipeline_integration_physical_deletion_before_collapse -v`
Expected: `FAIL` (current monolithic method doesn't support this yet)

- [ ] **Step 3: Refactor `_project_and_collapse_messages` to call Pipeline stages**

Replace the entire `_project_and_collapse_messages` method with:

```python
    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        """
        5-stage Pipeline: boundary → prescan → redaction → physical deletion → standard collapse.
        """
        if not messages:
            return []

        # Stage 1: Compute sliding window boundary
        boundary_index = self._stage_compute_boundary(messages)
        ctx = _CollapseContext(messages=messages, boundary_index=boundary_index)

        # Stage 2: Pre-scan window-out failed tools
        self._stage_prescan_failures(ctx)

        # Stage 3: Redaction (Linter failure handling)
        projected = self._stage_redaction(messages, ctx)

        # Stage 4: Physical deletion of failed pairs
        after_deletion = self._stage_physical_deletion(projected, ctx)

        # Stage 5: Standard collapse for remaining tools
        final = self._stage_standard_collapse(after_deletion, ctx)

        # Logging
        if ctx.redacted_count > 0 or ctx.kept_count > 0:
            logger.info(
                "\U0001F6E1\uFE0F Redaction: %d failures redacted, %d kept as correction clue. Kept call_ids: %s",
                ctx.redacted_count, ctx.kept_count, ctx.kept_call_ids
            )
        if ctx.deleted_call_ids:
            logger.info(
                "\U0001F5D1\uFE0F Paired physical deletion: %d failed pairs removed. Deleted call_ids: %s",
                len(ctx.deleted_call_ids), ctx.deleted_call_ids
            )

        return final
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py::test_pipeline_integration_physical_deletion_before_collapse -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "refactor(collapse): wire 5-stage pipeline into _project_and_collapse_messages"
```

---

## Task 8: Add `_log_collapse_results` and Finalize

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Extract logging to `_log_collapse_results`**

Replace inline logging in `_project_and_collapse_messages` with:

```python
    def _log_collapse_results(self, ctx: _CollapseContext) -> None:
        """Emit audit logs for redaction and physical deletion stages."""
        if ctx.redacted_count > 0 or ctx.kept_count > 0:
            logger.info(
                "\U0001F6E1\uFE0F Redaction: %d failures redacted, %d kept as correction clue. Kept call_ids: %s",
                ctx.redacted_count, ctx.kept_count, ctx.kept_call_ids
            )
        if ctx.deleted_call_ids:
            logger.info(
                "\U0001F5D1\uFE0F Paired physical deletion: %d failed pairs removed. Deleted call_ids: %s",
                len(ctx.deleted_call_ids), ctx.deleted_call_ids
            )
```

Update `_project_and_collapse_messages` to call `self._log_collapse_results(ctx)` instead of inline logs.

- [ ] **Step 2: Run all existing tests to ensure no regressions**

Run: `pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v`
Expected: All tests pass (6 existing + 10 new = 16 tests)

- [ ] **Step 3: Commit**

```bash
git add backend/app/agent/middleware/safe_merge_middleware.py
git commit -m "refactor(collapse): extract _log_collapse_results and finalize pipeline"
```

---

## Self-Review

### 1. Spec Coverage

| Proposal2.md Section | Task | Status |
|---------------------|------|--------|
| `_CollapseContext` | Task 1 | Covered |
| `_stage_compute_boundary` | Task 2 | Covered |
| `_stage_prescan_failures` | Task 3 | Covered |
| `_stage_redaction` | Task 4 | Covered |
| `_stage_physical_deletion` | Task 5 | Covered |
| `_stage_standard_collapse` | Task 5 | Covered |
| Pipeline wiring | Task 7 | Covered |
| Audit logging | Task 8 | Covered |
| Tests (8 matrix items) | Tasks 2-7 | Covered |

### 2. Placeholder Scan

- No "TBD", "TODO", "implement later" found.
- All steps include complete code.
- All test commands include expected output.

### 3. Type Consistency

- `_CollapseContext` fields: `deleted_call_ids: set[str]`, `kept_call_ids: set[str]` — consistent across all tasks.
- `_stage_redaction` returns `list[Any]` — consumed by `_stage_physical_deletion`.
- `_stage_physical_deletion` returns `list[Any]` — consumed by `_stage_standard_collapse`.
- `_stage_standard_collapse` mutates in-place but also returns `list[Any]` for pipeline chaining.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2025-01-13-pipeline-physical-deletion.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
