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
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
    
    assert f"[系统提示: {expected_date_str}]" in content
    assert content.endswith(f"[系统提示: {expected_date_str}]")
    assert "Base system prompt" in content


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
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    expected_date_str = f"当前日期: {now.strftime('%Y-%m-%d')} ({weekdays[now.weekday()]})"
    
    assert f"[系统提示: {expected_date_str}]" in content
    assert content.endswith(f"[系统提示: {expected_date_str}]")
    assert "Base system prompt" in content
    assert "This is __business_rag_context__ info" in content
    assert len(new_request.messages) == 0


def test_safe_merge_context_collapse_successful_query():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
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
    assert state["messages"][2].content == "[{'id': 1, 'data': 'old_1'}, {'id': 2, 'data': 'old_2'}]"
    
    # 2. Oldest query is collapsed correctly
    collapsed_tool_msg = new_request.messages[2]
    assert isinstance(collapsed_tool_msg, ToolMessage)
    assert collapsed_tool_msg.name == "sql_db_query"
    assert collapsed_tool_msg.tool_call_id == "call_old"
    assert collapsed_tool_msg.content == "[SQL execution successful. Result content collapsed. Re-run query if details are needed.]"

    # 3. scenario load tool is exempted (not collapsed)
    assert new_request.messages[5].content == "scenario template instructions"

    # 4. Recent query inside sliding window is NOT collapsed
    assert new_request.messages[8].content == "[{'id': 3, 'data': 'new_1'}]"


def test_safe_merge_context_collapse_failed_query():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
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
    assert collapsed_msg.content == "[SQL execution failed. Detailed error log collapsed. Re-run with corrected SQL if needed.]"


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
    
    assert new_request.messages[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[1].tool_calls[0]["args"]["query"] == "SELECT 1"
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
    assert new_request.messages[1].tool_calls[0]["args"]["query"] == "SELECT 1"
    assert new_request.messages[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # 2. Attempt 2 (Success) is kept untouched (sliding window is latest, so not collapsed)
    assert new_request.messages[3].content == "Trying SQL 2"
    assert new_request.messages[4].content == "[{'id': 1}]"
