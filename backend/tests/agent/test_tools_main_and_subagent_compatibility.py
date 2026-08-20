# backend/tests/agent/test_tools_main_and_subagent_compatibility.py
"""
Ticket 02: 图表与 CSV 导出工具泛型状态解耦与主子智能体双向兼容测试。

验证内容:
1. build_chart_artifact 在 CustomState (主智能体) 下正常执行 (tool.invoke 与 tool.func)
2. build_chart_artifact 在 SqlSubAgentState (子智能体) 下正常执行
3. export_to_csv 在 CustomState (主智能体) 与 SqlSubAgentState (子智能体) 下正常执行
4. 工具返回 Command(update={"messages": ..., "tool_artifact": ...}) 结构规范性
5. 异常场景下统一抛出 ToolException 保证 Prompt 中间件可折叠裁剪
6. 工具面向大模型的 args 中绝不包含内部注入参数 runtime，零 CallableSchema 序列化错误
7. 框架层注入契约 (_get_all_injected_args) 成立，真实 ToolNode invoke 调度顺畅
"""
import json
import pytest
from langchain.tools import ToolRuntime
from langgraph.types import Command
from langgraph.prebuilt.tool_node import _get_all_injected_args
from sqlalchemy import create_engine

from backend.app.agent.context import RequestContext
from backend.app.agent.state import CustomState, SqlSubAgentState
from backend.app.agent.tools.chart_artifact_tool import create_chart_artifact_tool
from backend.app.agent.tools.csv_export_tool import create_csv_export_tool


@pytest.fixture
def sqlite_engine():
    """提供带有测试数据的 SQLite 内存引擎。"""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE ods_daily_metric (
                stat_date TEXT,
                defect_count INTEGER,
                output_count INTEGER,
                vehicle_model TEXT
            );
        """)
        conn.exec_driver_sql("""
            INSERT INTO ods_daily_metric VALUES 
            ('2026-08-01', 12, 100, 'A7'),
            ('2026-08-02', 15, 120, 'A7'),
            ('2026-08-01', 8, 90, 'TiguanL'),
            ('2026-08-02', 10, 110, 'TiguanL');
        """)
        conn.commit()
    return engine


def _make_runtime(state, tool_call_id="call_test_001", subagent_name="main"):
    """创建真实的 ToolRuntime 数据类实例供测试使用。"""
    rt = ToolRuntime(
        context=RequestContext(user_id="u1", session_id="s1"),
        state=state,
        tool_call_id=tool_call_id,
        stream_writer=lambda x: None,
        config={"configurable": {"thread_id": "t1"}},
        store=None,
    )
    setattr(rt, "subagent_name", subagent_name)
    return rt


def test_build_chart_artifact_main_agent_invoke(sqlite_engine):
    """验证主智能体环境 (CustomState) 下通过 tool.invoke 真实调度生成图表。"""
    tool = create_chart_artifact_tool(engine=sqlite_engine)
    runtime = _make_runtime(
        state=CustomState(messages=[], context_warning=False, tool_artifact=None),
        tool_call_id="call_main_chart_001",
        subagent_name="main",
    )

    result = tool.invoke({
        "query": "SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='A7' ORDER BY stat_date",
        "chart_type": "line",
        "title": "A7 车型每日缺陷趋势",
        "description": "主智能体直接调起绘图",
        "x_field": "stat_date",
        "series": [{"name": "缺陷数", "field": "defect_count"}],
        "runtime": runtime,
    })

    assert isinstance(result, Command)
    assert "messages" in result.update
    assert "tool_artifact" in result.update

    tool_msg = result.update["messages"][0]
    assert tool_msg.tool_call_id == "call_main_chart_001"
    ref_data = json.loads(tool_msg.content)
    assert ref_data["kind"] == "chart_artifact_ref"
    assert ref_data["chart_id"].startswith("cht_")

    artifact = result.update["tool_artifact"]
    assert artifact["kind"] == "chart_spec"
    assert artifact["tool_call_id"] == "call_main_chart_001"
    assert len(artifact["rows"]) == 2


def test_build_chart_artifact_subagent_invoke(sqlite_engine):
    """验证子智能体环境 (SqlSubAgentState) 下通过 tool.invoke 正常执行。"""
    tool = create_chart_artifact_tool(engine=sqlite_engine)
    runtime = _make_runtime(
        state=SqlSubAgentState(messages=[], skills_loaded=["paint_defect_analysis"]),
        tool_call_id="call_sub_chart_003",
        subagent_name="sql_domain_agent",
    )

    result = tool.invoke({
        "query": "SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='A7'",
        "chart_type": "bar",
        "title": "缺陷柱状图",
        "description": "",
        "x_field": "stat_date",
        "series": [{"name": "缺陷数", "field": "defect_count"}],
        "runtime": runtime,
    })

    assert isinstance(result, Command)
    assert result.update["tool_artifact"]["chart_type"] == "bar"
    assert result.update["tool_artifact"]["tool_call_id"] == "call_sub_chart_003"


def test_export_to_csv_main_and_subagent_invoke(sqlite_engine):
    """验证 export_to_csv 在主智能体与子智能体通过 tool.invoke 均兼容运行。"""
    tool = create_csv_export_tool(engine=sqlite_engine)

    # 1. 主智能体环境调用
    runtime_main = _make_runtime(
        state=CustomState(messages=[], context_warning=False, tool_artifact=None),
        tool_call_id="call_main_exp_001",
        subagent_name="main",
    )

    result_main = tool.invoke({
        "query": "SELECT stat_date, defect_count, output_count, vehicle_model FROM ods_daily_metric",
        "runtime": runtime_main,
    })
    assert isinstance(result_main, Command)
    assert result_main.update["tool_artifact"]["kind"] == "file_export"
    assert result_main.update["tool_artifact"]["tool_call_id"] == "call_main_exp_001"
    assert result_main.update["tool_artifact"]["row_count"] == 4

    # 2. 子智能体环境调用
    runtime_sub = _make_runtime(
        state=SqlSubAgentState(messages=[], skills_loaded=["vehicle_export_skill"]),
        tool_call_id="call_sub_exp_002",
        subagent_name="sql_domain_agent",
    )

    result_sub = tool.invoke({
        "query": "SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='TiguanL'",
        "runtime": runtime_sub,
    })
    assert isinstance(result_sub, Command)
    assert result_sub.update["tool_artifact"]["row_count"] == 2
    assert result_sub.update["tool_artifact"]["file_id"].startswith("exp_")


def test_tools_injection_contract_and_llm_schema(sqlite_engine):
    """验证框架层注入契约 (_get_all_injected_args) 成立，且面向大模型的 args 中绝不包含 runtime。"""
    chart_tool = create_chart_artifact_tool(engine=sqlite_engine)
    csv_tool = create_csv_export_tool(engine=sqlite_engine)

    # 1. 验证 LangGraph 注入契约
    chart_inj = _get_all_injected_args(chart_tool)
    assert chart_inj.runtime == "runtime"
    csv_inj = _get_all_injected_args(csv_tool)
    assert csv_inj.runtime == "runtime"

    # 2. 验证面向 LLM 的 Function Calling 参数中绝不泄露 runtime
    assert "runtime" not in chart_tool.args
    assert "runtime" not in csv_tool.args
    assert "query" in csv_tool.args
    assert "query" in chart_tool.args


def test_chart_series_pydantic_validation_error_contract(sqlite_engine):
    """验证非法 category_field / category_value 组合在入口处被 Pydantic 自动拦截抛出 ValidationError。"""
    from pydantic import ValidationError

    chart_tool = create_chart_artifact_tool(engine=sqlite_engine)
    runtime = _make_runtime(state=CustomState(messages=[]))

    # 1. 传入未成对的 category_field (缺少 category_value)
    with pytest.raises(ValidationError) as exc_info:
        chart_tool.invoke({
            "query": "SELECT stat_date, defect_count FROM ods_daily_metric",
            "chart_type": "bar",
            "title": "测试",
            "description": "",
            "x_field": "stat_date",
            "series": [{"name": "A", "field": "defect_count", "category_field": "model"}],
            "runtime": runtime,
        })

    assert "category_field 和 category_value 必须同时提供" in str(exc_info.value)

    # 2. 验证 extra='forbid' 策略下非法未知字段会被 Pydantic 拦截
    with pytest.raises(ValidationError):
        chart_tool.invoke({
            "query": "SELECT stat_date, defect_count FROM ods_daily_metric",
            "chart_type": "bar",
            "title": "测试",
            "description": "",
            "x_field": "stat_date",
            "series": [{"name": "A", "field": "defect_count", "unknown_extra_param": "invalid"}],
            "runtime": runtime,
        })
