# Phase 4 详细设计规范 (Detailed Design Specification)
## 主题：联调与数据库持久化存储验证 (Joint Debugging & Persistence Verification)

本规范书定义了 **阶段 4：联调与数据库持久化存储验证** 的测试与验证方案。核心目标是证明经过一至三阶段的重构后，大文本 RAG 辅助信息已被物理隔绝在 `messages` 对话历史之外，从而彻底阻止了数据库（如 `PostgresSaver`）在每次会话存档时的历史消息存储暴增，同时确保状态的序列化与流转能够正常进行。

---

## 1. 核心验证要点 (Verification Objectives)

### 1.1 历史消息列表绝对无 RAG 污染
*   **断言**：在 LangGraph 产生的每个 `checkpoint` 存档中，`checkpoint["channel_values"]["messages"]` 列表里的所有消息，均不含有 `"__business_rag_context__"` 或大规模 DDL 表结构文本。
*   **目的**：确保对话历史保持纯净，数据库在持久化消息序列时无需存储重复的垃圾大文本。

### 1.2 RAG 状态覆盖更新 (Last-Wins)
*   **断言**：在 `checkpoint["channel_values"]` 字典中，`lexicon_context` 和 `rag_context` 仅保留**最近一轮**的数据。
*   **目的**：利用 `CustomState` 中的 `_last_wins` Reducer 覆盖机制，确保不论对话进行到第十几轮，数据库中仅存储最新的 RAG 上下文快照，而不是像 `messages`（使用 `add_messages` 叠加）一样随轮次无限增长。

### 1.3 序列化与反序列化完整性
*   **断言**：Agent 流程在包含 `PostgresSaver` / `MemorySaver` 持久化机制下，多轮对话能够正常加载并恢复状态，不会因为 `lexicon_context` 的结构变化而导致 JSON 序列化（Serialization）或反序列化失败。

---

## 2. 验证脚本设计 ([test_persistence_integration.py](file:///f:/000_dev/Python/workplace/rearch_agent/.tree/features/agent-llamaindex-rag/backend/tests/agent/test_persistence_integration.py))

我们将新建一个专用的集成验证测试用例，模拟多轮对话并检查底层 Checkpointer 的实际存储数据。

### 2.1 验证用例伪代码设计

```python
# backend/tests/agent/test_persistence_integration.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agent.service import SQLAgentService
from backend.app.agent.state import CustomState

@pytest.mark.asyncio
async def test_agent_persistence_without_message_pollution():
    # 1. 模拟数据库连接和向量检索器
    mock_db = MagicMock()
    mock_db.dialect = "postgresql"
    
    mock_retriever = MagicMock()
    mock_doc = MagicMock()
    mock_doc.document.metadata = {"term": "TestPersist", "domain": "Verification"}
    mock_doc.document.page_content = "Verification content text"
    mock_doc.score = 0.9
    mock_retriever.retrieve = MagicMock(return_value=[mock_doc])
    
    # 2. 模拟 LLM 模型调用，直接返回 AIMessage
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="查询验证已通过"))

    # 3. 使用内存持久化存储器 MemorySaver
    memory_saver = MemorySaver()

    # 4. Mock 词典检索器，防止在测试期间发起外部网络请求
    with patch("backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever") as mock_lexicon_class, \
         patch("backend.app.agent.service.ChatOpenAI", return_value=mock_llm), \
         patch("backend.app.agent.service.create_business_retriever_and_reranker", return_value=(mock_retriever, None)):
         
        mock_lexicon_retriever = AsyncMock()
        mock_lexicon_class.return_value = mock_lexicon_retriever
        mock_lexicon_retriever.retrieve_all.return_value = {
            "tables": [], "values": [], "rows": []
        }

        # 5. 实例化 SQLAgentService，注入 memory_saver
        service = SQLAgentService(
            use_ollama=False,
            checkpointer=memory_saver,
            auto_initialize=True
        )
        
        # 覆写 service 内部 db 为 mock_db
        service.db = mock_db

        # 6. 第一轮对话交互
        config = {"configurable": {"thread_id": "test_verification_thread"}}
        input_state = {"messages": [HumanMessage(content="查询 Defect 数据")]}
        
        # 运行 Agent 流程
        graph = service.agent
        await graph.ainvoke(input_state, config=config)

        # 7. 从 Saver 中打捞最新存档的 Checkpoint 并进行严格的断言验证
        state_history = list(memory_saver.list(config))
        assert len(state_history) > 0
        
        latest_checkpoint = state_history[0].checkpoint
        channel_values = latest_checkpoint.get("channel_values", {})
        
        # 确认 lexicon_context 与 rag_context 状态正常保存
        assert "lexicon_context" in channel_values
        assert "formatted_text" in channel_values["lexicon_context"]
        assert "Verification content text" in channel_values["lexicon_context"]["formatted_text"]
        
        # 🚨 核心安全绿线断言：messages 历史列表中绝不包含大段 RAG 上下文
        messages = channel_values.get("messages", [])
        for msg in messages:
            content = getattr(msg, "content", "")
            # 无论如何，消息内容都不应被 RAG 中间件修改插入
            assert "__business_rag_context__" not in str(content)
            assert "Verification content text" not in str(content)

        print("🎉 阶段 4：联调与数据库持久化存储验证成功！历史消息列表中完全无 RAG 大文本污染。")
```

---

## 3. 验证与回归计划 (Verification & Regression Plan)

1.  **运行持久化集成测试**：
    `conda activate py312_agent; python -m pytest backend/tests/agent/test_persistence_integration.py -v`
    **预期结果**：运行通过，打印持久化验证成功日志。
2.  **本地运行回归测试**：
    运行 `python -m pytest` 回归整个项目的测试集，确保在本地 FastAPI 环境以及 LangGraph 开发环境中各项中间件能够完美和谐地协同工作。
