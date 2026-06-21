import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from langgraph.types import Command
from backend.app.services import SQLAgentService

@pytest.mark.asyncio
async def test_agent_resume_process():
    # 1. 构造 Mock 的 CompiledGraph 实例
    mock_agent = MagicMock()
    
    from langchain_core.messages import AIMessage

    # 模拟 astream 返回 of chunks
    async def mock_astream(*args, **kwargs):
        # 产生 messages 块 (用于 token 事件)
        msg = AIMessage(content="resumed response")
        yield ("messages", (msg, {}))
        
        # 产生 updates 块 (用于完结内容赋值和 final 事件)
        yield ("updates", {
            "agent": {
                "messages": [msg]
            }
        })
        
    mock_agent.astream = mock_astream
    
    # Mock aget_state to return an empty state that can be awaited
    mock_state = MagicMock()
    mock_state.next = []
    mock_state.tasks = []
    mock_agent.aget_state = AsyncMock(return_value=mock_state)
    
    # 2. 构造 SQLAgentService 实例
    mock_core = MagicMock()
    mock_core.agent = mock_agent
    mock_core.checkpointer = MagicMock()
    mock_core._use_ollama = False
    
    service = SQLAgentService(mock_core)
    
    # 3. 运行 process_stream_resume，收集事件
    session_id = "test-session-id"
    answers = {"question?": "answers"}
    
    events = []
    async for event in service.process_stream_resume(session_id, answers):
        events.append(event)
        
    # 4. 验证是否产生了 final 事件且内容包含 resume response
    assert len(events) > 0
    final_event = next((e for e in events if e["type"] == "final"), None)
    assert final_event is not None
    assert final_event["content"] == "resumed response"
