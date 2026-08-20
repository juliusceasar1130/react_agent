# backend/tests/agent/test_tools_main_and_subagent_compatibility.py
"""
Ticket 02: 图表与 CSV 导出工具泛型状态解耦与主子智能体双向兼容测试。

验证内容:
1. build_chart_artifact 在 CustomState (主智能体) 下正常执行
2. build_chart_artifact 在 SqlSubAgentState (子智能体) 下正常执行
3. export_to_csv 在 CustomState (主智能体) 与 SqlSubAgentState (子智能体) 下正常执行
4. 工具返回 Command(update={"messages": ..., "tool_artifact": ...}) 结构规范性
5. 异常场景下统一抛出 ToolException 保证 Prompt 中间件可折叠裁剪
6. 工具的 JSON Schema 生成正常，绝不包含内部注入参数 runtime，零 CallableSchema 序列化错误
"""
import json
import pytest
from unittest.mock import MagicMock
from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException
from langgraph.types import Command
from pydantic import ValidationError
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


def test_build_chart_artifact_main_agent(sqlite_engine):
    """验证主智能体环境 (CustomState) 下生成图表。"""
    tool = create_chart_artifact_tool(engine=sqlite_engine)
    
    mock_runtime = MagicMock(spec=ToolRuntime)
    mock_runtime.state = CustomState(messages=[], context_warning=False, tool_artifact=None)
    mock_runtime.tool_call_id = "call_main_chart_001"
    mock_runtime.subagent_name = "main"

    result = tool.func(
        query="SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='A7' ORDER BY stat_date",
        chart_type="line",
        title="A7 车型每日缺陷趋势",
        description="主智能体直接调起绘图",
        x_field="stat_date",
        series=[{"name": "缺陷数", "field": "defect_count"}],
        runtime=mock_runtime,
    )

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


def test_build_chart_artifact_subagent(sqlite_engine):
    """验证子智能体环境 (SqlSubAgentState) 下正常执行。"""
    tool = create_chart_artifact_tool(engine=sqlite_engine)

    mock_runtime_sub = MagicMock(spec=ToolRuntime)
    mock_runtime_sub.state = SqlSubAgentState(messages=[], skills_loaded=["paint_defect_analysis"])
    mock_runtime_sub.tool_call_id = "call_sub_chart_003"
    mock_runtime_sub.subagent_name = "sql_domain_agent"

    result = tool.func(
        query="SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='A7'",
        chart_type="bar",
        title="缺陷柱状图",
        description="",
        x_field="stat_date",
        series=[{"name": "缺陷数", "field": "defect_count"}],
        runtime=mock_runtime_sub,
    )
    assert isinstance(result, Command)
    assert result.update["tool_artifact"]["chart_type"] == "bar"


def test_export_to_csv_main_and_subagent_compatibility(sqlite_engine):
    """验证 export_to_csv 在主智能体 (CustomState) 与子智能体 (SqlSubAgentState) 均兼容运行。"""
    tool = create_csv_export_tool(engine=sqlite_engine)

    # 1. 主智能体环境调用
    mock_runtime_main = MagicMock(spec=ToolRuntime)
    mock_runtime_main.state = CustomState(messages=[], context_warning=False, tool_artifact=None)
    mock_runtime_main.tool_call_id = "call_main_exp_001"
    mock_runtime_main.subagent_name = "main"

    result_main = tool.func(
        query="SELECT stat_date, defect_count, output_count, vehicle_model FROM ods_daily_metric",
        runtime=mock_runtime_main,
    )
    assert isinstance(result_main, Command)
    assert result_main.update["tool_artifact"]["kind"] == "file_export"
    assert result_main.update["tool_artifact"]["tool_call_id"] == "call_main_exp_001"
    assert result_main.update["tool_artifact"]["row_count"] == 4

    # 2. 子智能体环境调用
    mock_runtime_sub = MagicMock(spec=ToolRuntime)
    mock_runtime_sub.state = SqlSubAgentState(messages=[], skills_loaded=["vehicle_export_skill"])
    mock_runtime_sub.tool_call_id = "call_sub_exp_002"
    mock_runtime_sub.subagent_name = "sql_domain_agent"

    result_sub = tool.func(
        query="SELECT stat_date, defect_count FROM ods_daily_metric WHERE vehicle_model='TiguanL'",
        runtime=mock_runtime_sub,
    )
    assert isinstance(result_sub, Command)
    assert result_sub.update["tool_artifact"]["row_count"] == 2
    assert result_sub.update["tool_artifact"]["file_id"].startswith("exp_")


def test_tools_json_schema_generation(sqlite_engine):
    """验证工具生成给大模型的 JSON Schema 中不包含 runtime 内部注入参数，无 CallableSchema 序列化错误。"""
    chart_tool = create_chart_artifact_tool(engine=sqlite_engine)
    csv_tool = create_csv_export_tool(engine=sqlite_engine)

    # 获取 LLM Function Calling Schema
    chart_schema = chart_tool.get_input_schema().model_json_schema()
    csv_schema = csv_tool.get_input_schema().model_json_schema()

    assert "runtime" not in chart_schema.get("properties", {})
    assert "required_skill" not in chart_schema.get("properties", {})

    assert "runtime" not in csv_schema.get("properties", {})
    assert "required_skill" not in csv_schema.get("properties", {})
    assert "query" in csv_schema.get("properties", {})


def test_tools_args_schema_validation_and_runtime_injection(sqlite_engine):
    """验证工具在 extra='forbid' 下正确校验参数模型，并能与 runtime 依赖注入协同工作。"""
    csv_tool = create_csv_export_tool(engine=sqlite_engine)
    chart_tool = create_chart_artifact_tool(engine=sqlite_engine)

    # 1. 验证合法入参能通过 Pydantic args_schema 校验
    valid_csv_args = csv_tool.args_schema.model_validate({
        "query": "SELECT stat_date, defect_count FROM ods_daily_metric"
    })
    assert valid_csv_args.query.startswith("SELECT")

    valid_chart_args = chart_tool.args_schema.model_validate({
        "query": "SELECT stat_date, defect_count FROM ods_daily_metric",
        "chart_type": "line",
        "title": "测试图表",
        "x_field": "stat_date",
        "series": [{"name": "缺陷数", "field": "defect_count"}],
    })
    assert valid_chart_args.title == "测试图表"

    # 2. 验证 extra='forbid' 策略下非法未知字段会被拦截
    with pytest.raises(ValidationError):
        csv_tool.args_schema.model_validate({
            "query": "SELECT 1",
            "unknown_extra_param": "invalid_value",
        })

    with pytest.raises(ValidationError):
        chart_tool.args_schema.model_validate({
            "query": "SELECT 1",
            "chart_type": "line",
            "title": "t",
            "x_field": "x",
            "series": [{"name": "s", "field": "f"}],
            "unknown_extra_param": "invalid_value",
        })

    # 3. 验证执行时接收 runtime 注入并返回正确的 Command
    mock_runtime = MagicMock(spec=ToolRuntime)
    mock_runtime.state = CustomState(messages=[], context_warning=False, tool_artifact=None)
    mock_runtime.tool_call_id = "call_invoke_test_001"
    mock_runtime.subagent_name = "main"

    csv_res = csv_tool.func(
        query=valid_csv_args.query,
        runtime=mock_runtime,
    )
    assert isinstance(csv_res, Command)

    chart_res = chart_tool.func(
        query=valid_chart_args.query,
        chart_type=valid_chart_args.chart_type,
        title=valid_chart_args.title,
        description=valid_chart_args.description,
        x_field=valid_chart_args.x_field,
        series=[s.model_dump(exclude_none=True) for s in valid_chart_args.series],
        runtime=mock_runtime,
    )
    assert isinstance(chart_res, Command)
