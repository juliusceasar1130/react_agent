import pytest
import datetime
from langchain_core.messages import SystemMessage
from langchain.agents.middleware.types import ModelRequest

from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
from backend.app.agent.state import CustomState

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
    
    assert "<system_rules>" in content
    assert "</system_rules>" in content
    assert "<runtime_context>" in content
    assert "</runtime_context>" in content
    
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
    
    assert "<system_rules>" in content
    assert "</system_rules>" in content
    assert "<runtime_context>" in content
    assert "</runtime_context>" in content
    
    assert "Base system prompt" in content.split("</system_rules>")[0]
    assert "This is __business_rag_context__ info" in content.split("<runtime_context>")[1]
    assert f"[系统提示: {expected_date_str}]" in content.split("<runtime_context>")[1]
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
    
    middleware = PromptCompilerMiddleware()
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
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # Error message is now physically deleted (more aggressive than collapse)
    assert len(new_request.messages) == 4  # H0 + M1, M2, M3
    assert all(not (isinstance(m, ToolMessage) and m.tool_call_id == "call_bad") for m in new_request.messages)


def test_safe_merge_redacts_past_failures_keeps_last_n():
    """With keep_count=3, the oldest failure beyond the last 3 is redacted; latest 3 are kept."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain.agents.middleware.types import ModelRequest
    
    messages = [
        HumanMessage(content="Query active users"),
        # Attempt 1: Failed (oldest, beyond keep_count=3 → redacted)
        AIMessage(content="Trying SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),
        
        # Attempt 2: Failed (kept — within last 3)
        AIMessage(content="Trying SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_2"),
        
        # Attempt 3: Failed (kept — within last 3)
        AIMessage(content="Trying SQL 3", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 3"}, "id": "call_3"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SYN-002", name="sql_db_query", tool_call_id="call_3"),
        
        # Attempt 4: Failed (latest, kept — within last 3)
        AIMessage(content="Trying SQL 4", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 4"}, "id": "call_4"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SYN-003", name="sql_db_query", tool_call_id="call_4"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # Attempt 1 (oldest, beyond keep_count=3) is redacted
    assert new_request.messages[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[1].tool_calls[0]["args"]["query"] == "SELECT 1"
    assert new_request.messages[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # Attempt 2 (within last 3) is preserved
    assert new_request.messages[3].content == "Trying SQL 2"
    assert new_request.messages[4].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-001"
    
    # Attempt 3 (within last 3) is preserved
    assert new_request.messages[5].content == "Trying SQL 3"
    assert new_request.messages[6].content == "X-SQL-LINTER-STATUS: FAILED\nError: SYN-002"
    
    # Attempt 4 (latest, within last 3) is preserved
    assert new_request.messages[7].content == "Trying SQL 4"
    assert new_request.messages[8].content == "X-SQL-LINTER-STATUS: FAILED\nError: SYN-003"


def test_safe_merge_redacts_all_failures_on_success():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from langchain.agents.middleware.types import ModelRequest
    
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
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # Assertions:
    # 1. Attempt 1 is redacted
    assert new_request.messages[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert new_request.messages[1].tool_calls[0]["args"]["query"] == "SELECT 1"
    assert new_request.messages[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # 2. Attempt 2 (Success) is kept untouched (sliding window is latest, so not collapsed)
    assert new_request.messages[3].content == "Trying SQL 2"
    assert new_request.messages[4].content == "[{'id': 1}]"


def test_stage_compute_boundary_protects_last_n_human_messages():
    from langchain_core.messages import HumanMessage, AIMessage
    
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
    
    middleware = PromptCompilerMiddleware()
    boundary = middleware._stage_compute_boundary(messages)
    # H5 is last, H4 second-to-last, H3 third-to-last (protect_turns=3)
    # H3 is at index 4 (0-indexed)
    assert boundary == 4


def test_stage_redaction_keeps_last_n_failures():
    """With keep_count=3, 4 failures → oldest 1 redacted, latest 3 kept."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        AIMessage(content="SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),

        AIMessage(content="SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-002", name="sql_db_query", tool_call_id="call_2"),

        AIMessage(content="SQL 3", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 3"}, "id": "call_3"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-003", name="sql_db_query", tool_call_id="call_3"),

        AIMessage(content="SQL 4", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 4"}, "id": "call_4"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-004", name="sql_db_query", tool_call_id="call_4"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)

    # Oldest failure (call_1, beyond keep_count=3) is redacted
    assert result[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    assert result[1].content == "[Invalid SQL attempt. Redacted to save context space.]"

    # Failures 2-4 (within last 3) are preserved
    assert result[4].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-002"
    assert result[3].content == "SQL 2"

    assert result[6].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-003"
    assert result[5].content == "SQL 3"

    assert result[8].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-004"
    assert result[7].content == "SQL 4"


def test_stage_redaction_cross_domain_success_no_pollution():
    """Domain A success (before last HumanMessage) must not redact Domain B failures."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        # Domain A (before last HumanMessage)
        HumanMessage(content="Domain A question"),
        AIMessage(content="SQL A1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT A1"}, "id": "call_a1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_a1"),
        AIMessage(content="SQL A2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT A2"}, "id": "call_a2"}]),
        ToolMessage(content="[{\"id\": 1}]", name="sql_db_query", tool_call_id="call_a2"),  # Domain A SUCCESS

        # Domain B (after last HumanMessage — current ReAct loop)
        HumanMessage(content="Domain B question"),
        AIMessage(content="SQL B1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT B1"}, "id": "call_b1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_b1"),
        AIMessage(content="SQL B2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT B2"}, "id": "call_b2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SYN-002", name="sql_db_query", tool_call_id="call_b2"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)

    # Domain A failure (call_a1) is redacted (not in current loop's kept set)
    assert result[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"

    # Domain B failures are BOTH kept (cross-domain success did NOT pollute)
    assert result[7].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-001"
    assert result[6].content == "SQL B1"

    assert result[9].content == "X-SQL-LINTER-STATUS: FAILED\nError: SYN-002"
    assert result[8].content == "SQL B2"


def test_stage_redaction_success_in_current_loop_redacts_all():
    """When the current ReAct loop has a success, all failures in that loop are redacted."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        AIMessage(content="SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),

        AIMessage(content="SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-002", name="sql_db_query", tool_call_id="call_2"),

        AIMessage(content="SQL 3", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 3"}, "id": "call_3"}]),
        ToolMessage(content="[{\"id\": 1}]", name="sql_db_query", tool_call_id="call_3"),  # SUCCESS
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)

    # Both failures are redacted (success in current loop → all failures redacted)
    assert result[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    assert result[1].content == "[Invalid SQL attempt. Redacted to save context space.]"

    assert result[4].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    assert result[3].content == "[Invalid SQL attempt. Redacted to save context space.]"

    # Success is preserved
    assert result[6].content == "[{\"id\": 1}]"
    assert result[5].content == "SQL 3"


def test_stage_prescan_sql_linter_failure():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_fail"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=2)
    middleware._stage_prescan_failures(ctx)

    assert "call_fail" in ctx.deleted_call_ids


def test_stage_prescan_chart_runtime_failure():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Chart"),
        ToolMessage(content="X-CHART-STATUS: FAILED\nError: bad json", name="build_chart_artifact", tool_call_id="call_chart"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=2)
    middleware._stage_prescan_failures(ctx)

    assert "call_chart" in ctx.deleted_call_ids


def test_stage_prescan_success_not_deleted():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="[{'id': 1, 'name': 'Alice'}]", name="sql_db_query", tool_call_id="call_ok"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=1)
    middleware._stage_prescan_failures(ctx)

    assert "call_ok" not in ctx.deleted_call_ids


def test_stage_physical_deletion_removes_failed_pairs():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        AIMessage(content="SQL fail", tool_calls=[{"name": "sql_db_query", "args": {"query": "bad"}, "id": "call_fail"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED", name="sql_db_query", tool_call_id="call_fail"),

        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=3, deleted_call_ids={"call_fail"})
    result = middleware._stage_physical_deletion(messages, ctx)

    # Both AIMessage and ToolMessage for call_fail should be removed
    assert len(result) == 4  # H1, H2, H3, H4 (M1, M2, M3 plus original H1)
    assert all(not (isinstance(m, ToolMessage) and m.tool_call_id == "call_fail") for m in result)


def test_stage_physical_deletion_partial_filter_keeps_ai_message():
    """If AIMessage has multiple tool_calls and only one fails, keep the AIMessage."""
    from langchain_core.messages import AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        AIMessage(content="Multi call", tool_calls=[
            {"name": "sql_db_query", "args": {"query": "bad"}, "id": "call_fail"},
            {"name": "search_saved_correct_tool_uses", "args": {}, "id": "call_ok"}
        ]),
        ToolMessage(content="Error", name="sql_db_query", tool_call_id="call_fail"),
        ToolMessage(content="OK", name="search_saved_correct_tool_uses", tool_call_id="call_ok"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0, deleted_call_ids={"call_fail"})
    result = middleware._stage_physical_deletion(messages, ctx)

    # AIMessage should be kept with only the successful tool_call
    assert len(result) == 2
    assert isinstance(result[0], AIMessage)
    assert len(result[0].tool_calls) == 1
    assert result[0].tool_calls[0]["id"] == "call_ok"


def test_stage_standard_collapse_sql_success():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query"),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="call_ok"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=2)
    result = middleware._stage_standard_collapse(messages, ctx)

    assert result[1].content == "[SQL execution successful. Result content collapsed. Re-run query if details are needed.]"


def test_stage_standard_collapse_chart_success():
    from langchain_core.messages import HumanMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Chart"),
        ToolMessage(content='{"data": []}', name="build_chart_artifact", tool_call_id="call_chart"),
        HumanMessage(content="M1"),
        HumanMessage(content="M2"),
        HumanMessage(content="M3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=2)
    result = middleware._stage_standard_collapse(messages, ctx)

    assert result[1].content == "[Chart generated successfully. ECharts JSON config collapsed.]"


def test_pipeline_integration_physical_deletion_before_collapse():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

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

    middleware = PromptCompilerMiddleware()
    result = middleware._project_and_collapse_messages(messages)

    # call_fail pair should be physically deleted
    assert all(not (isinstance(m, ToolMessage) and m.tool_call_id == "call_fail") for m in result)

    # call_ok should be collapsed (not deleted, but content replaced)
    ok_msg = next(m for m in result if isinstance(m, ToolMessage) and m.tool_call_id == "call_ok")
    assert "collapsed" in ok_msg.content.lower()


def test_stage_redaction_keeps_linter_and_runtime_mixed_failures():
    """验证 Linter 报错和数据库运行期报错混合重试时，在 keep_count=3 的限制内，两者都被原样保留不折叠。"""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query active users"),
        # Attempt 1: Linter 拦截失败 (错误 1)
        AIMessage(content="Trying SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED\nError: SEM-001", name="sql_db_query", tool_call_id="call_1"),
        
        # Attempt 2: 数据库 UndefinedColumn 报错 (错误 2)
        AIMessage(content="Trying SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "SELECT 2"}, "id": "call_2"}]),
        ToolMessage(content="Error: (psycopg2.errors.UndefinedColumn) column not found", name="sql_db_query", tool_call_id="call_2"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)

    # 验证：因为当前依然没有成功 SQL，且两个错误都在最近 3 次以内，两者都必须保留不折叠！
    assert result[2].content == "X-SQL-LINTER-STATUS: FAILED\nError: SEM-001"
    assert result[1].content == "Trying SQL 1"
    
    assert result[4].content == "Error: (psycopg2.errors.UndefinedColumn) column not found"
    assert result[3].content == "Trying SQL 2"


def test_stage_redaction_keeps_active_failures_after_success():
    """测试多步 SQL 场景下，成功 SQL 之后的最新失败尝试属于活跃线索，不应被折叠，而成功之前的陈旧失败应被折叠。"""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    from backend.app.agent.middleware.prompt_compiler_middleware import _CollapseContext

    messages = [
        HumanMessage(content="Query profile and logs"),
        # 1. 步骤一的失败 (应被折叠，因为其后已经成功了)
        AIMessage(content="SQL 1", tool_calls=[{"name": "sql_db_query", "args": {"query": "bad 1"}, "id": "call_1"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED", name="sql_db_query", tool_call_id="call_1"),
        
        # 2. 步骤一改对成功 (分水岭)
        AIMessage(content="SQL 2", tool_calls=[{"name": "sql_db_query", "args": {"query": "ok 2"}, "id": "call_2"}]),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="call_2"),
        
        # 3. 步骤二开始尝试，最新失败 (活跃失败，必须受到 keep_count 保护保留)
        AIMessage(content="SQL 3", tool_calls=[{"name": "sql_db_query", "args": {"query": "bad 3"}, "id": "call_3"}]),
        ToolMessage(content="X-SQL-LINTER-STATUS: FAILED", name="sql_db_query", tool_call_id="call_3"),
    ]

    middleware = PromptCompilerMiddleware()
    ctx = _CollapseContext(messages=messages, boundary_index=0)
    result = middleware._stage_redaction(messages, ctx)

    # 验证：分水岭之前的 call_1 被折叠
    assert result[1].content == "[Invalid SQL attempt. Redacted to save context space.]"
    assert result[2].content == "[SQL validation failed by Linter. Previous invalid attempt redacted to save context space.]"
    
    # 验证：分水岭之后的 call_3 完好保留作为线索
    assert result[5].content == "SQL 3"
    assert result[6].content == "X-SQL-LINTER-STATUS: FAILED"


def test_prompt_compiler_lexicon_retrieval_window_in_preservation():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟处于滑动窗口内部的检索，应完好保留
    messages = [
        HumanMessage(content="Query table schema"),
        AIMessage(content="Let me check schema", tool_calls=[{"name": "search_db_table_schema", "args": {"query": "ods.process_areas"}, "id": "call_schema"}]),
        ToolMessage(content="CREATE TABLE ods.process_areas (id VARCHAR);", name="search_db_table_schema", tool_call_id="call_schema"),
        HumanMessage(content="Helpful query"),
    ]
    
    state = CustomState(messages=messages)
    request = ModelRequest(
        model=None,
        messages=messages,
        system_message=SystemMessage(content="Base system prompt"),
        state=state
    )
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 验证窗口内消息完整，不被删除
    assert len(new_request.messages) == 4
    assert new_request.messages[2].content == "CREATE TABLE ods.process_areas (id VARCHAR);"
    assert new_request.messages[1].tool_calls[0]["name"] == "search_db_table_schema"


def test_prompt_compiler_lexicon_retrieval_window_out_ultimate_deletion():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟超出滑动窗口边界的检索工具调用，应当成对物理删除
    messages = [
        HumanMessage(content="Old query"),
        AIMessage(content="Search old table DDL", tool_calls=[{"name": "search_db_table_schema", "args": {"query": "old_table"}, "id": "call_old_schema"}]),
        ToolMessage(content="CREATE TABLE old_table (id INT);", name="search_db_table_schema", tool_call_id="call_old_schema"),
        
        # 3 个 HumanMessage 确保其被推到窗口外
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
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 验证窗口外检索对已完全被物理删除（从 6 条消息缩减为 4 条，去掉了 AIMessage 和 ToolMessage 对）
    assert len(new_request.messages) == 4  # H0, M1, M2, M3
    for msg in new_request.messages:
        if isinstance(msg, ToolMessage):
            assert msg.tool_call_id != "call_old_schema"
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            assert all(tc["id"] != "call_old_schema" for tc in msg.tool_calls)


def test_prompt_compiler_lexicon_retrieval_mixed_tool_calls_deletion():
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
    # 模拟并行调用：一个检索工具（需删除）和一个成功SQL工具（需保留折叠）
    messages = [
        HumanMessage(content="Find and Query"),
        AIMessage(
            content="Check schema and data",
            tool_calls=[
                {"name": "search_db_table_schema", "args": {"query": "t1"}, "id": "c_schema"},
                {"name": "sql_db_query", "args": {"query": "SELECT * FROM t1"}, "id": "c_sql"}
            ]
        ),
        ToolMessage(content="CREATE TABLE t1 (id INT);", name="search_db_table_schema", tool_call_id="c_schema"),
        ToolMessage(content="[{'id': 1}]", name="sql_db_query", tool_call_id="c_sql"),
        
        # 推动其滑出窗口
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
    
    middleware = PromptCompilerMiddleware()
    new_request = middleware._modify_request(request)
    
    # 检索对应当删除，SQL成功对应当折叠
    # 消息列表中，检索的 ToolMessage (index 2) 被剔除，SQL 的 ToolMessage (index 3) 被折叠
    tool_msgs = [m for m in new_request.messages if isinstance(m, ToolMessage)]
    # 只剩下 SQL 成功查询对应的 ToolMessage，且被成功折叠
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "c_sql"
    assert tool_msgs[0].content == "[SQL execution successful. Result content collapsed. Re-run query if details are needed.]"
    
    # 并行 AIMessage 应该只保留 SQL 调用，剥离检索调用
    ai_msgs = [m for m in new_request.messages if isinstance(m, AIMessage)]
    assert len(ai_msgs) == 1
    assert len(ai_msgs[0].tool_calls) == 1
    assert ai_msgs[0].tool_calls[0]["id"] == "c_sql"
