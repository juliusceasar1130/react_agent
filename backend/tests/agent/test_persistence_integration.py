# backend/tests/agent/test_persistence_integration.py
import pytest
import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from langchain_deepseek import ChatDeepSeek
from backend.app.agent.service import SQLAgentService
from backend.app.agent.state import CustomState

@pytest.mark.asyncio
async def test_agent_persistence_without_message_pollution():
    # 1. 模拟数据库连接
    mock_db = MagicMock()
    mock_db.dialect = "postgresql"
    
    # 2. 模拟 RAG 向量检索器返回文档
    from langchain_core.documents import Document
    mock_retriever = MagicMock()
    real_doc = Document(
        page_content="Verification content text",
        metadata={"term": "TestPersist", "domain": "Verification"}
    )
    mock_scored_result = MagicMock()
    mock_scored_result.document = real_doc
    mock_scored_result.score = 0.9
    mock_retriever.retrieve = MagicMock(return_value=[mock_scored_result])
    
    # 3. 模拟 LLM 模型调用，直接返回完成的 AIMessage
    mock_llm = MagicMock(spec=ChatDeepSeek)
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.bind.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="查询验证已通过"))

    # 4. 使用内存持久化存储器 MemorySaver
    memory_saver = MemorySaver()

    # 5. Mock 词典检索器，防止在测试期间发起外部网络请求
    with patch("backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever") as mock_lexicon_class, \
         patch("backend.app.agent.llm.QwenChatDeepSeek", return_value=mock_llm), \
         patch("backend.app.agent.service.create_business_retriever_and_reranker", return_value=(mock_retriever, None)):
         
        mock_lexicon_retriever = AsyncMock()
        mock_lexicon_class.return_value = mock_lexicon_retriever
        mock_lexicon_retriever.retrieve_all.return_value = {
            "tables": [],
            "values": [],
            "rows": []
        }

        # 6. 实例化 SQLAgentService，注入 memory_saver，不加载实际连接
        service = SQLAgentService(
            use_ollama=False,
            checkpointer=memory_saver,
            auto_initialize=True
        )
        
        # 覆写 service 内部 db 为 mock_db
        service.db = mock_db

        # 7. 模拟第一轮对话交互
        config = {"configurable": {"thread_id": "test_verification_thread"}}
        input_state = {"messages": [HumanMessage(content="查询 Defect 数据")]}
        
        # 运行 Agent 流程
        graph = service.agent
        await graph.ainvoke(input_state, config=config)

        # 8. 从 Saver 中打捞最新存档的 Checkpoint 并进行严格的断言验证
        state_history = list(memory_saver.list(config))
        assert len(state_history) > 0
        
        latest_checkpoint = state_history[0].checkpoint
        channel_values = latest_checkpoint.get("channel_values", {})
        
        # 确认 lexicon_context 状态正常保存
        assert "lexicon_context" in channel_values
        assert "formatted_text" in channel_values["lexicon_context"]
        assert "Verification content text" in channel_values["lexicon_context"]["formatted_text"]
        
        # 🚨 核心安全绿线断言：messages 历史列表中绝不包含大段 RAG 上下文
        messages = channel_values.get("messages", [])
        for msg in messages:
            content = getattr(msg, "content", "")
            # 无论是何种消息类型，消息内容都不应被 RAG 中间件修改插入大段参考信息
            assert "__business_rag_context__" not in str(content)
            assert "Verification content text" not in str(content)
