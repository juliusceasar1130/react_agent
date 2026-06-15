# SQL Agent Read-Time Context Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a read-time projection middleware that collapses old SQL execution and search results beyond the sliding window to optimize context size and prompt caching without breaking Vue 3 frontend UI data tables.

**Architecture:** We will intercept the `ModelRequest` right before calling the LLM API inside `SafeMergeSystemMiddleware`. We clone the message history, slide back from the end to protect the last 3 turns of user interaction, and collapse collapsible tool results (like `sql_db_query`) into extremely short semantic placeholders while preserving raw metadata (`tool_call_id`, `role`, `name`) for API verification safety.

**Tech Stack:** Python 3.12, FastAPI, LangChain, LangGraph, pytest

---

### Task 1: Add Configuration Settings for Collapse Window

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Write the config setting test**

Create/Add this test at the end of `backend/app/test_config.py` (or if it doesn't exist, create it):
Create: `backend/app/test_config.py`
```python
from backend.app.config import settings

def test_context_collapse_config():
    # Verify default config parameter exists and is 3
    assert hasattr(settings, "llm_context_collapse_protect_turns")
    assert settings.llm_context_collapse_protect_turns == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
conda run -n py312_agent pytest backend/app/test_config.py -v
```
Expected output:
```text
AttributeError: 'Settings' object has no attribute 'llm_context_collapse_protect_turns'
```

- [ ] **Step 3: Modify config.py to add the setting**

Modify: `backend/app/config.py` (add property inside the `Settings` class)
```python
    llm_context_collapse_protect_turns: int = 3
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
conda run -n py312_agent pytest backend/app/test_config.py -v
```
Expected output:
```text
backend/app/test_config.py . [100%]
1 passed in 0.15s
```

- [ ] **Step 5: Commit config changes**

Run:
```bash
git add backend/app/config.py backend/app/test_config.py
git commit -m "feat: add llm_context_collapse_protect_turns setting"
```

---

### Task 2: Write Failing Tests for Context Collapse Middleware

**Files:**
- Modify: `backend/app/agent/middleware/test_safe_merge_middleware.py`

- [ ] **Step 1: Add tests for sliding window, collapsing, and exemption**

Append the following test cases to `backend/app/agent/middleware/test_safe_merge_middleware.py`:
```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from backend.app.agent.middleware.safe_merge_middleware import SafeMergeSystemMiddleware
from backend.app.agent.state import CustomState
from langchain.agents.middleware.types import ModelRequest

def test_safe_merge_context_collapse_successful_query():
    # History containing multiple turns. The oldest sql_db_query should be collapsed.
    # The recent ones (within 3 protected human messages) should remain untouched.
    messages = [
        # Round 1: Oldest query (should be collapsed)
        HumanMessage(content="Query oldest data"),
        AIMessage(content="Let me check", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT * FROM old_table"}, "id": "call_old"}]),
        ToolMessage(content="[{'id': 1, 'data': 'old_1'}, {'id': 2, 'data': 'old_2'}]", name="sql_db_query", tool_call_id="call_old"),
        
        # Round 2: Human Message 3 (Start of sliding window)
        HumanMessage(content="Human message 3"),
        AIMessage(content="Checking scenario", tool_calls=[{"name": "load_scenario", "args": {"skill_name": "x", "scenario_name": "y"}, "id": "call_scenario"}]),
        ToolMessage(content="scenario template instructions", name="load_scenario", tool_call_id="call_scenario"),
        
        # Round 3: Human Message 2 (Inside sliding window)
        HumanMessage(content="Human message 2"),
        AIMessage(content="Querying new table", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT * FROM new_table"}, "id": "call_new"}]),
        ToolMessage(content="[{'id': 3, 'data': 'new_1'}]", name="sql_db_query", tool_call_id="call_new"),
        
        # Round 4: Human Message 1 (Latest, inside sliding window)
        HumanMessage(content="Show final summary"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    # Assertions:
    # 1. State messages (source of truth for DB/UI) must remain fully untouched
    assert state.messages[2].content == "[{'id': 1, 'data': 'old_1'}, {'id': 2, 'data': 'old_2'}]"
    
    # 2. Oldest query is collapsed correctly
    collapsed_tool_msg = new_request.messages[2]
    assert isinstance(collapsed_tool_msg, ToolMessage)
    assert collapsed_tool_msg.name == "sql_db_query"
    assert collapsed_tool_msg.tool_call_id == "call_old"
    assert "SQL execution successful. Result content collapsed: 2 rows" in collapsed_tool_msg.content
    assert "SELECT * FROM old_table" in collapsed_tool_msg.content

    # 3. scenario load tool is exempted (not collapsed)
    assert new_request.messages[5].content == "scenario template instructions"

    # 4. Recent query inside sliding window is NOT collapsed
    assert new_request.messages[8].content == "[{'id': 3, 'data': 'new_1'}]"

def test_safe_merge_context_collapse_failed_query():
    messages = [
        HumanMessage(content="Query failed table"),
        AIMessage(content="Checking error", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT * FROM bad"}, "id": "call_bad"}]),
        # A long error log
        ToolMessage(content="Error: (psycopg2.errors.UndefinedTable) relation 'bad' does not exist\nTraceback info here...", name="sql_db_query", tool_call_id="call_bad"),
        
        # 3 protected human messages to push the error out of the sliding window
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = SafeMergeSystemMiddleware()
    new_request = middleware._modify_request(request)
    
    # Error message must be collapsed and summarize the first line only
    collapsed_msg = new_request.messages[2]
    assert isinstance(collapsed_msg, ToolMessage)
    assert "SQL execution failed. Detailed error log collapsed" in collapsed_msg.content
    assert "Error: (psycopg2.errors.UndefinedTable) relation 'bad' does not exist" in collapsed_msg.content
    assert "Traceback info here..." not in collapsed_msg.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
conda run -n py312_agent pytest backend/app/agent/middleware/test_safe_merge_middleware.py -k "collapse"
```
Expected output:
```text
FAILED backend/app/agent/middleware/test_safe_merge_middleware.py::test_safe_merge_context_collapse_successful_query
FAILED backend/app/agent/middleware/test_safe_merge_context_collapse_failed_query
```

- [ ] **Step 3: Commit the test file**

Run:
```bash
git add backend/app/agent/middleware/test_safe_merge_middleware.py
git commit -m "test: add test cases for P0 context collapse read-time projection"
```

---

### Task 3: Implement Context Collapse Read-Time Projection

**Files:**
- Modify: `backend/app/agent/middleware/safe_merge_middleware.py`

- [ ] **Step 1: Write minimal code implementation**

Modify `backend/app/agent/middleware/safe_merge_middleware.py` by:
1. Importing required message types and config settings.
2. Defining `COLLAPSIBLE_TOOLS` whitelist.
3. Adding helper methods `_project_and_collapse_messages` and `_extract_core_error`.
4. Updating `_modify_request` to apply the collapse transformation.

Implementation details:
```python
# Insert imports at the top
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from backend.app.config import settings

# Define Collapsible tools whitelist
COLLAPSIBLE_TOOLS = {
    "sql_db_query",
    "search_saved_correct_tool_uses",
    "build_chart_artifact",
    "export_to_csv",
    "export_query_to_csv"
}

# Add helper methods in SafeMergeSystemMiddleware class:
    def _extract_core_error(self, content: str) -> str:
        """Extract the first line of the error content, capped at 120 chars."""
        first_line = content.split("\n")[0] if content else "Unknown database error"
        return first_line[:120]

    def _project_and_collapse_messages(self, messages: list[Any]) -> list[Any]:
        """Memory-only projection of messages, collapsing old tool results outside the sliding window."""
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

        # 3. Collapse collapsible tool messages outside the sliding window
        from backend.app.agent.tools.sql_tools import _estimate_row_count
        for idx in range(boundary_index):
            msg = projected[idx]
            if isinstance(msg, ToolMessage) and msg.name in COLLAPSIBLE_TOOLS:
                # Process sql_db_query collapse
                if msg.name == "sql_db_query":
                    content_str = str(msg.content)
                    is_err = "Error" in content_str or "exception" in content_str.lower()
                    
                    if is_err:
                        core_err = self._extract_core_error(content_str)
                        # We must preserve the ToolMessage container, id and role. Just modify content.
                        projected[idx] = ToolMessage(
                            content=f"[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed. (Error: {core_err})]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                    else:
                        row_count = _estimate_row_count(content_str)
                        
                        # Find corresponding query from the parent AIMessage tool_calls
                        associated_sql = "SELECT ..."
                        if idx > 0 and isinstance(projected[idx-1], AIMessage):
                            tool_calls = getattr(projected[idx-1], "tool_calls", [])
                            if tool_calls:
                                associated_sql = tool_calls[0].get("args", {}).get("query", "SELECT ...")
                        
                        projected[idx] = ToolMessage(
                            content=f"[SQL execution successful. Result content collapsed: {row_count} rows. Query: {associated_sql}. Re-run query if details are needed.]",
                            name=msg.name,
                            tool_call_id=msg.tool_call_id
                        )
                
                # Process search_saved_correct_tool_uses collapse
                elif msg.name == "search_saved_correct_tool_uses":
                    projected[idx] = ToolMessage(
                        content="[SQL examples retrieved and collapsed: reference examples shown in earlier step.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                
                # Process chart generation collapse
                elif msg.name == "build_chart_artifact":
                    projected[idx] = ToolMessage(
                        content="[Chart generated successfully. ECharts JSON config collapsed.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )
                
                # Process CSV export collapse
                elif msg.name in ("export_to_csv", "export_query_to_csv"):
                    projected[idx] = ToolMessage(
                        content="[CSV export completed and collapsed. User has already received the download link.]",
                        name=msg.name,
                        tool_call_id=msg.tool_call_id
                    )

        return projected
```

And update `_modify_request`:
```python
    def _modify_request(self, request: ModelRequest) -> ModelRequest:
        self._inject_thinking_config(request)
        
        raw_messages = list(request.messages) if request.messages else []
        # Run projection collapse first
        projected_messages = self._project_and_collapse_messages(raw_messages)

        filtered_messages = []
        rag_texts = []

        # Scan the projected messages to merge RAG messages
        for msg in projected_messages:
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
                    rag_text = _get_string_content(msg)
                    if rag_text:
                        rag_texts.append(rag_text)
                    continue

            filtered_messages.append(msg)

        # Build final unified SystemMessage and override Request
        sys_text = _get_string_content(request.system_message)
        import datetime
        now = datetime.datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
        date_prompt = f"\n\n[系统提示: {date_str}]"

        if rag_texts:
            merged_rag_text = "\n\n".join(rag_texts)
            merged_content = f"{sys_text}\n\n{merged_rag_text}{date_prompt}"
            new_system_message = SystemMessage(content=merged_content)
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

Run:
```bash
conda run -n py312_agent pytest backend/app/agent/middleware/test_safe_merge_middleware.py -v
```
Expected output:
```text
============================= 4 passed in 1.82s =============================
```

- [ ] **Step 3: Commit implementation**

Run:
```bash
git add backend/app/agent/middleware/safe_merge_middleware.py
git commit -m "feat: implement read-time projection context collapse for P0 tools"
```
