import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from backend.app.services import SQLAgentService

@pytest.mark.asyncio
async def test_stream_execution_loop_message_filtering():
    """测试 _stream_execution_loop 应该只将 AIMessage 的文本作为 token 发送给前端"""
    mock_core = MagicMock()
    
    # 模拟 astream 返回多个节点不同类型的消息块
    async def mock_astream(*args, **kwargs):
        # 1. 模拟 RAG 系统消息块（应该被过滤）
        yield ("messages", (SystemMessage(content="__business_rag_context__ RAG Context Info"), {"langgraph_node": "rag"}))
        # 2. 模拟 SQL 执行 Tool 返回消息块（应该被过滤，不发送 token，但会触发 tool_result 事件）
        yield ("messages", (ToolMessage(content="SQL query results: wip_count 3", tool_call_id="call_1"), {"langgraph_node": "tools"}))
        # 3. 模拟 AI 正常文本回答块（应该被保留并发出 token）
        yield ("messages", (AIMessage(content="根据查询，L2面漆在制车辆共3台。"), {"langgraph_node": "agent"}))
    
    mock_core.agent.astream = mock_astream
    mock_core.agent.aget_state = AsyncMock(return_value=None)
    
    service = SQLAgentService(mock_core)
    
    events = []
    # 运行流式循环并收集产生的事件
    async for event in service._stream_execution_loop("test-sess-99", {}, "L2面漆在制情况"):
        events.append(event)
        
    # 过滤出 token 事件
    tokens = [e for e in events if e.get("type") == "token"]
    
    # 【断言 1】：应该只发出一个 AI 消息的 token
    assert len(tokens) == 1
    assert tokens[0]["text"] == "根据查询，L2面漆在制车辆共3台。"
    
    # 【断言 2】：SystemMessage 和 ToolMessage 的文本绝对不能流出为 token
    assert not any("__business_rag_context__" in t["text"] for t in tokens)
    assert not any("SQL query results" in t["text"] for t in tokens)
