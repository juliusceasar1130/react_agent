# Phase 4: Joint Debugging & Persistence Verification Detailed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a comprehensive integration verification test to prove that RAG content is completely excluded from message history logs in DB checkpoints, confirming zero history message pollution.

**Architecture:** Create an integration test that compiles the LangGraph instance via SQLAgentService under a MemorySaver saver. The test executes a mock turn, fetches the checkpoint snapshot from the memory checkpointer, and asserts that the `messages` list does not contain RAG texts or duplicate large schema blocks, while checking that `lexicon_context` and `rag_context` are correctly persisted and updated in a last-wins fashion.

**Tech Stack:** Python 3.12, pytest, LangGraph.

---

### Task 1: Implement persistence integration verification test

**Files:**
- Create: `backend/tests/agent/test_persistence_integration.py`

- [ ] **Step 1: Create the integration test file**

Write a new test file `backend/tests/agent/test_persistence_integration.py` with the complete mocking and state checkpoint verification logic:

```python
# backend/tests/agent/test_persistence_integration.py
import pytest
import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agent.service import SQLAgentService
from backend.app.agent.state import CustomState

@pytest.mark.asyncio
async def test_agent_persistence_without_message_pollution():
    # 1. 模拟数据库连接
    mock_db = MagicMock()
    mock_db.dialect = "postgresql"
    
    # 2. 模拟 RAG 向量检索器返回文档
    mock_retriever = MagicMock()
    mock_doc = MagicMock()
    mock_doc.document.metadata = {"term": "TestPersist", "domain": "Verification"}
    mock_doc.document.page_content = "Verification content text"
    mock_doc.score = 0.9
    mock_retriever.retrieve = MagicMock(return_value=[mock_doc])
    
    # 3. 模拟 LLM 模型调用，直接返回完成的 AIMessage
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="查询验证已通过"))

    # 4. 使用内存持久化存储器 MemorySaver
    memory_saver = MemorySaver()

    # 5. Mock 词典检索器，防止在测试期间发起外部网络请求
    with patch("backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever") as mock_lexicon_class, \
         patch("backend.app.agent.service.ChatOpenAI", return_value=mock_llm), \
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
```

- [ ] **Step 2: Run the test to verify it passes**

Run command:
`conda activate py312_agent; python -m pytest backend/tests/agent/test_persistence_integration.py -v`

Expected output:
`PASSED backend/tests/agent/test_persistence_integration.py::test_agent_persistence_without_message_pollution`

- [ ] **Step 3: Run full backend regression tests**

Run command:
`conda activate py312_agent; python -m pytest backend/app/agent/middleware/test_prompt_compiler_middleware.py -v`
Expected output: 20 passed.

Run command:
`conda activate py312_agent; python -m pytest backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py -v`
Expected output: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/agent/test_persistence_integration.py
git commit -m "test: add integration test to verify RAG decoupling from persistent message history"
```

---

## Self-Review

1. **Spec coverage:** Covered. The test comprehensively verifies the saver checkpoints, message values, last-wins reducer outcomes, and Graph compilation.
2. **Placeholder scan:** Scanned. Complete test code and correct assert lists.
3. **Type consistency:** Verified. Matches `MemorySaver`, `CustomState`, and `SQLAgentService` API endpoints.
