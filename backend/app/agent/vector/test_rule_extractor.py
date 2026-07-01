import pytest
from unittest.mock import MagicMock, patch
from backend.app.agent.vector.rule_extractor import (
    ExtractionContext,
    BaseFilter,
    PipelineManager
)

class DummyPassFilter(BaseFilter):
    def execute(self, context: ExtractionContext) -> bool:
        return True

class DummyFailFilter(BaseFilter):
    def execute(self, context: ExtractionContext) -> bool:
        context.is_rejected = True
        context.reject_reason = "dummy_failed"
        return False

def test_pipeline_manager_passes_all_filters():
    """测试所有过滤器都通过时，管道成功返回"""
    db_mock = MagicMock()
    manager = PipelineManager(filters=[DummyPassFilter()])
    payload = manager.process("msg-1", db_mock)
    
    assert payload is not None
    assert payload["message_id"] == "msg-1"

def test_pipeline_manager_stops_on_fail_filter():
    """测试任何过滤器失败时，管道中止并记录原因"""
    db_mock = MagicMock()
    manager = PipelineManager(filters=[DummyPassFilter(), DummyFailFilter()])
    payload = manager.process("msg-2", db_mock)
    
    assert payload is None

def test_safety_warning_filter():
    """测试安全过滤器拦截违规 SQL 或带安全警告的消息"""
    from backend.app.agent.vector.rule_extractor import SafetyWarningFilter, ExtractionContext
    
    # 1. 模拟 SQL 含有 DROP
    ctx1 = ExtractionContext("m1", MagicMock())
    ctx1.tool_result = "SUCCESS"
    msg_mock1 = MagicMock()
    msg_mock1.content = "SQL: DROP TABLE chat_messages"
    ctx1.target_message = msg_mock1
    
    f = SafetyWarningFilter()
    assert f.execute(ctx1) is False
    assert "DROP" in ctx1.reject_reason
    
    # 2. 模拟执行结果包含 Safety Warning 警告
    ctx2 = ExtractionContext("m2", MagicMock())
    msg_mock2 = MagicMock()
    msg_mock2.content = "SELECT 1"
    ctx2.target_message = msg_mock2
    ctx2.tool_result = "Safety Warning: query blocked"
    assert f.execute(ctx2) is False
    
    # 3. 正常情况通过
    ctx3 = ExtractionContext("m3", MagicMock())
    msg_mock3 = MagicMock()
    msg_mock3.content = "SELECT * FROM users"
    ctx3.target_message = msg_mock3
    ctx3.tool_result = "[{'id': 1}]"
    assert f.execute(ctx3) is True

def test_empty_result_filter():
    """测试空结果集拦截"""
    from backend.app.agent.vector.rule_extractor import EmptyResultFilter, ExtractionContext
    
    f = EmptyResultFilter()
    
    # 1. 模拟空列表返回
    ctx1 = ExtractionContext("m1", MagicMock())
    ctx1.tool_result = "[]"
    assert f.execute(ctx1) is False
    
    # 2. 模拟非 JSON 的非结构化空结果
    ctx2 = ExtractionContext("m2", MagicMock())
    ctx2.tool_result = ""
    assert f.execute(ctx2) is False
    
    # 3. 有效结果通过
    ctx3 = ExtractionContext("m3", MagicMock())
    ctx3.tool_result = "[{'total': 12}]"
    assert f.execute(ctx3) is True

def test_single_sql_filter():
    """测试单步 SQL 过滤规则"""
    from backend.app.agent.vector.rule_extractor import SingleSqlFilter, ExtractionContext
    import json
    
    f = SingleSqlFilter()
    
    # 1. 模拟存在多个 sql_db_query 的多步骤查询（包含两个 SQL 调用）
    ctx1 = ExtractionContext("m1", MagicMock())
    mock_msg1 = MagicMock()
    mock_msg1.tool_calls = json.dumps([
        {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT 1"}},
        {"id": "t2", "name": "sql_db_query", "args": {"query": "SELECT 2"}}
    ])
    mock_msg1.tool_results = json.dumps({
        "t1": "res1",
        "t2": "res2"
    })
    ctx1.target_message = mock_msg1
    assert f.execute(ctx1) is False
    assert "多步查询" in ctx1.reject_reason or "多个" in ctx1.reject_reason
    
    # 2. 模拟 SQL 执行报错的消息
    ctx2 = ExtractionContext("m2", MagicMock())
    mock_msg2 = MagicMock()
    mock_msg2.tool_calls = json.dumps([
        {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT 1"}}
    ])
    mock_msg2.tool_results = json.dumps({
        "t1": "Error: column 'x' does not exist"
    })
    ctx2.target_message = mock_msg2
    assert f.execute(ctx2) is False
    assert "报错" in ctx2.reject_reason or "Error" in ctx2.reject_reason
    
    # 3. 正常单步成功 SQL
    ctx3 = ExtractionContext("m3", MagicMock())
    mock_msg3 = MagicMock()
    mock_msg3.tool_calls = json.dumps([
        {"id": "t1", "name": "sql_db_query", "args": {"query": "SELECT * FROM users"}}
    ])
    mock_msg3.tool_results = json.dumps({
        "t1": "[{'id': 1}]"
    })
    ctx3.target_message = mock_msg3
    assert f.execute(ctx3) is True
    assert ctx3.extracted_sql == "SELECT * FROM users"
    assert ctx3.tool_result == "[{'id': 1}]"

@patch("backend.app.agent.vector.rule_extractor.get_messages_by_session")
def test_topology_backtrack_filter(mock_get_messages):
    """测试基于 tool_call_id 的精准拓扑回溯"""
    from backend.app.agent.vector.rule_extractor import TopologyBacktrackFilter, ExtractionContext
    import json
    
    # 构造会话消息链历史：
    # M1: User 原始提问 ("查2产线的出车数")
    # M2: Assistant 中断提问 ("请确认哪天？", tool_calls=[AskUserQuestion(id='ask-1')])
    # M3: User 回答澄清 ("今天", tool_results={'ask-1': '今天'})
    # M4: Assistant 最终回复 ("SELECT ...", tool_calls=[sql_db_query(id='sql-1')]) (这就是收藏的 target_message)
    
    m1 = MagicMock()
    m1.id = "m1"
    m1.role = "user"
    m1.content = "查2产线的出车数"
    
    m2 = MagicMock()
    m2.id = "m2"
    m2.role = "assistant"
    m2.content = "我们想和您确认哪天？"
    m2.tool_calls = json.dumps([{"id": "ask-1", "name": "AskUserQuestion", "args": {}}])
    
    m3 = MagicMock()
    m3.id = "m3"
    m3.role = "user"
    m3.content = "[澄清回答] 今天"
    m3.tool_results = json.dumps({"ask-1": "今天"})
    
    m4 = MagicMock()
    m4.id = "m4"
    m4.role = "assistant"
    m4.content = "数据结果..."
    m4.tool_calls = json.dumps([{"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT 1"}}])
    m4.tool_results = json.dumps({"sql-1": "[{'val': 1}]"})
    
    mock_get_messages.return_value = [m1, m2, m3, m4]
    
    ctx = ExtractionContext("m4", MagicMock())
    ctx.target_message = m4
    
    f = TopologyBacktrackFilter()
    assert f.execute(ctx) is True
    
    # 校验精准回溯的链条
    assert len(ctx.history_messages) == 4
    assert ctx.history_messages[0].content == "查2产线的出车数"
    assert ctx.history_messages[1].content == "我们想和您确认哪天？"
    assert ctx.history_messages[2].content == "[澄清回答] 今天"
    assert ctx.history_messages[3].content == "数据结果..."
    assert ctx.raw_user_query == "查2产线的出车数 [澄清提问: 我们想和您确认哪天？ -> 澄清回答: 今天]"

def test_domain_filter():
    """测试 required_skill 的业务域属性提取"""
    from backend.app.agent.vector.rule_extractor import DomainFilter, ExtractionContext
    import json
    
    f = DomainFilter()
    
    # 1. 正常包含 legacy skill 参数
    ctx1 = ExtractionContext("m1", MagicMock())
    mock_msg1 = MagicMock()
    mock_msg1.tool_calls = json.dumps([
        {"id": "t1", "name": "load_skill", "args": {"skill": "paint_shop"}}
    ])
    ctx1.target_message = mock_msg1
    assert f.execute(ctx1) is True
    assert ctx1.domain == "paint_shop"
    
    # 2. 正常包含 required_skill 在 sql_db_query (第一优先级)
    ctx_sql = ExtractionContext("m_sql", MagicMock())
    mock_msg_sql = MagicMock()
    mock_msg_sql.tool_calls = json.dumps([
        {"id": "t2", "name": "sql_db_query", "args": {"query": "SELECT 1", "required_skill": "paint_shop_defect_analysis"}},
        {"id": "t1", "name": "load_skill", "args": {"skill_name": "general_other"}}
    ])
    ctx_sql.target_message = mock_msg_sql
    assert f.execute(ctx_sql) is True
    assert ctx_sql.domain == "paint_shop_defect_analysis"

    # 3. 包含 skill_name 在 load_skill
    ctx_name = ExtractionContext("m_name", MagicMock())
    mock_msg_name = MagicMock()
    mock_msg_name.tool_calls = json.dumps([
        {"id": "t1", "name": "load_skill", "args": {"skill_name": "paint_shop_defect_analysis"}}
    ])
    ctx_name.target_message = mock_msg_name
    assert f.execute(ctx_name) is True
    assert ctx_name.domain == "paint_shop_defect_analysis"

    # 4. 不包含任何 domain/skill 字段，默认为 general
    ctx2 = ExtractionContext("m2", MagicMock())
    mock_msg2 = MagicMock()
    mock_msg2.tool_calls = json.dumps([
        {"id": "t2", "name": "sql_db_query", "args": {}}
    ])
    ctx2.target_message = mock_msg2
    assert f.execute(ctx2) is True
    assert ctx2.domain == "general"

@patch("backend.app.agent.vector.rule_extractor.get_messages_by_session")
def test_pipeline_integration(mock_get_messages):
    """测试完整提取器管道链路集成"""
    from backend.app.agent.vector.rule_extractor import DEFAULT_EXTRACTOR_PIPELINE
    import json
    
    # 构造会话消息链历史：
    # M1: User 原始提问 ("查2产线的出车数")
    # M2: Assistant 最终回复 ("SELECT ...", tool_calls=[sql_db_query(id='sql-1')]) (这就是收藏的 target_message)
    
    m1 = MagicMock()
    m1.id = "m1"
    m1.role = "user"
    m1.content = "查2产线的出车数"
    
    m2 = MagicMock()
    m2.id = "m2"
    m2.role = "assistant"
    m2.content = "数据结果..."
    m2.tool_calls = json.dumps([
        {"id": "t_skill", "name": "load_skill", "args": {"skill": "paint_shop"}},
        {"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT * FROM users"}}
    ])
    m2.tool_results = json.dumps({
        "t_skill": "loaded",
        "sql-1": "[{'id': 1}]"
    })
    
    # Mock crud.get_message inside PipelineManager
    with patch("backend.app.crud.get_message", return_value=m2):
        mock_get_messages.return_value = [m1, m2]
        db_mock = MagicMock()
        
        payload = DEFAULT_EXTRACTOR_PIPELINE.process("m2", db_mock)
        assert payload is not None
        assert payload["message_id"] == "m2"
        assert payload["extracted_sql"] == "SELECT * FROM users"
        assert payload["tool_result"] == "[{'id': 1}]"
        assert payload["domain"] == "paint_shop"
        assert payload["raw_user_query"] == "查2产线的出车数"


def test_safety_warning_filter_disabled():
    """测试安全过滤器在被禁用时直接通过"""
    from backend.app.agent.vector.rule_extractor import SafetyWarningFilter, ExtractionContext
    from backend.app.config import settings

    ctx = ExtractionContext("m1", MagicMock())
    ctx.tool_result = "SUCCESS"
    msg_mock = MagicMock()
    msg_mock.content = "SQL: DROP TABLE chat_messages"
    ctx.target_message = msg_mock
    
    f = SafetyWarningFilter()
    
    # 用 patch 修改配置，模拟被禁用
    with patch.object(settings, "rule_extractor_safety_enabled", False):
        assert f.execute(ctx) is True


@patch("backend.app.agent.vector.rule_extractor.get_messages_by_session")
def test_topology_backtrack_filter_disabled(mock_get_messages):
    """测试拓扑回溯在被禁用时，仅回退 1 轮"""
    from backend.app.agent.vector.rule_extractor import TopologyBacktrackFilter, ExtractionContext
    from backend.app.config import settings
    import json

    m1 = MagicMock()
    m1.id = "m1"
    m1.role = "user"
    m1.content = "查2产线的出车数"
    
    m2 = MagicMock()
    m2.id = "m2"
    m2.role = "assistant"
    m2.content = "我们想和您确认哪天？"
    m2.tool_calls = json.dumps([{"id": "ask-1", "name": "AskUserQuestion", "args": {}}])
    
    m3 = MagicMock()
    m3.id = "m3"
    m3.role = "user"
    m3.content = "[澄清回答] 今天"
    m3.tool_results = json.dumps({"ask-1": "今天"})
    
    m4 = MagicMock()
    m4.id = "m4"
    m4.role = "assistant"
    m4.content = "数据结果..."
    m4.tool_calls = json.dumps([{"id": "sql-1", "name": "sql_db_query", "args": {"query": "SELECT 1"}}])
    m4.tool_results = json.dumps({"sql-1": "[{'val': 1}]"})
    
    mock_get_messages.return_value = [m1, m2, m3, m4]
    
    ctx = ExtractionContext("m4", MagicMock())
    ctx.target_message = m4
    
    f = TopologyBacktrackFilter()
    
    # 模拟 backtracking 禁用，仅回溯 1 轮（此时 history 应该只有 m3 和 m4）
    with patch.object(settings, "rule_extractor_backtrack_enabled", False):
        assert f.execute(ctx) is True
        assert len(ctx.history_messages) == 2
        assert ctx.history_messages[0].id == "m3"
        assert ctx.history_messages[1].id == "m4"
        assert ctx.raw_user_query == "[澄清回答] 今天"
