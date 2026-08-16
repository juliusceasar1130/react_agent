import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, ChatSession, ChatMessage
from backend.app.schemas import (
    MessageCreate,
    MessageResponse,
    ToolArtifactStreamEvent,
    FinalStreamEvent,
)
from backend.app import crud
from backend.app.routers.chat import _encode_sse


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # 创建一个测试会话
    chat_sess = ChatSession(id="test-sess-1", title="Test Session")
    session.add(chat_sess)
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_tool_artifacts_model_and_crud(db_session):
    """测试 ChatMessage 的 tool_artifacts 列及 CRUD 读写"""
    sample_artifacts = {
        "call_sql_1": {
            "kind": "query_result",
            "columns": ["id", "count"],
            "rows": [[1, 100]],
            "row_count": 1,
            "subagent_id": "call_sql_1",
            "subagent_name": "sql_domain_agent",
            "tool_call_id": "call_sql_1"
        },
        "chart_123": {
            "kind": "chart_spec",
            "chart_id": "chart_123",
            "title": "生产趋势",
            "subagent_id": "call_viz_2",
            "subagent_name": "data_analysis_agent"
        }
    }
    artifacts_json = json.dumps(sample_artifacts, ensure_ascii=False)

    msg_create = MessageCreate(
        session_id="test-sess-1",
        role="assistant",
        content="查询完成，图表与表格如下",
        tool_artifacts=artifacts_json
    )

    created = crud.create_message(db_session, msg_create)
    assert created.id is not None
    assert created.tool_artifacts == artifacts_json

    # 测试通过 get_messages_by_session 获取
    msgs = crud.get_messages_by_session(db_session, "test-sess-1")
    assert len(msgs) == 1
    assert msgs[0].tool_artifacts == artifacts_json

    # 测试 Pydantic Response 序列化
    resp_dto = MessageResponse.model_validate(msgs[0])
    assert resp_dto.tool_artifacts == artifacts_json


def test_tool_artifact_stream_events():
    """测试 SSE 流式事件中工件及溯源信封"""
    art_event = ToolArtifactStreamEvent(
        type="tool_artifact",
        artifact={"kind": "chart_spec", "chart_id": "chart_999"},
        subagent_id="call_viz_1",
        subagent_name="data_analysis_agent",
        tool_call_id="call_viz_1"
    )
    encoded = _encode_sse(art_event)
    assert '"type":"tool_artifact"' in encoded or '"type": "tool_artifact"' in encoded
    assert "call_viz_1" in encoded
    assert "data_analysis_agent" in encoded
    assert "chart_999" in encoded

    # FinalStreamEvent
    final_event = FinalStreamEvent(
        type="final",
        content="完成",
        tool_artifacts={
            "call_viz_1": {"kind": "chart_spec", "chart_id": "chart_999"}
        }
    )
    encoded_final = _encode_sse(final_event)
    assert '"type":"final"' in encoded_final or '"type": "final"' in encoded_final
    assert "chart_999" in encoded_final


def test_multi_artifact_same_subagent_collision_free(db_session):
    """测试同一个子智能体产生多个工件时，以各自内部 tool_call_id 为 Key 独立存储无冲突"""
    subagent_id = "task_subagent_001"
    subagent_name = "sql_domain_agent"

    # 工具 1：SQL 查询
    sql_artifact = {
        "kind": "query_result",
        "tool_call_id": "call_sql_query_abc",
        "columns": ["dept", "salary"],
        "rows": [["IT", 20000]],
        "subagent_id": subagent_id,
        "subagent_name": subagent_name,
    }

    # 工具 2：图表生成
    chart_artifact = {
        "kind": "chart_spec",
        "tool_call_id": "call_chart_spec_xyz",
        "chart_id": "chart_dept_salary",
        "title": "部门薪资",
        "subagent_id": subagent_id,
        "subagent_name": subagent_name,
    }

    # 模拟聚合过程（以 tool_call_id 为优先 Key）
    accumulated_artifacts = {}
    for art in [sql_artifact, chart_artifact]:
        key = art.get("tool_call_id") or art.get("chart_id") or "default"
        accumulated_artifacts[key] = art

    # 验证两个工件互不冲刷覆盖
    assert len(accumulated_artifacts) == 2
    assert "call_sql_query_abc" in accumulated_artifacts
    assert "call_chart_spec_xyz" in accumulated_artifacts
    assert accumulated_artifacts["call_sql_query_abc"]["kind"] == "query_result"
    assert accumulated_artifacts["call_chart_spec_xyz"]["kind"] == "chart_spec"

    # 落库并重新查询验证
    msg = crud.create_message(
        db_session,
        MessageCreate(
            session_id="test-sess-1",
            role="assistant",
            content="图表与数据均已就绪",
            tool_artifacts=json.dumps(accumulated_artifacts, ensure_ascii=False)
        )
    )
    loaded = crud.get_messages_by_session(db_session, "test-sess-1")
    target = next(m for m in loaded if m.id == msg.id)
    reconstructed = json.loads(target.tool_artifacts)
    assert len(reconstructed) == 2
    assert reconstructed["call_sql_query_abc"]["rows"] == [["IT", 20000]]
    assert reconstructed["call_chart_spec_xyz"]["chart_id"] == "chart_dept_salary"

