# backend/tests/agent/test_context_api_transient_flow.py
"""
Phase 1 - Ticket 01: Context API 瞬态数据通道与 Checkpoint 零污染测试。

验证内容:
1. RequestContext 契约声明与字段完整性
2. BusinessRagMiddleware 在运行时将检索结果注入 RequestContext，且不向 State 回写大体量检索对象
3. BusinessRagMiddleware 发生检索异常时，向 runtime.context 回退空值且 0 字节写入 State
4. Checkpointer 持久化快照中 100% 不包含 lexicon_context 与 rag_context
5. RagPromptInjectorMiddleware 与 PromptCompilerMiddleware 能够无缝从 request.runtime.context 获取 DDL 与 RAG 文本
"""
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.documents import Document
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest
from langchain.agents.middleware.types import Runtime
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agent.context import RequestContext
from backend.app.agent.state import CustomState, SqlSubAgentState
from backend.app.agent.middleware.rag_middleware import BusinessRagMiddleware
from backend.app.agent.middleware.rag_prompt_injector_middleware import RagPromptInjectorMiddleware
from backend.app.agent.middleware.prompt_compiler_middleware import PromptCompilerMiddleware
from backend.app.agent.vector.base import BaseRetriever, ScoredDocument


class DummyRetriever(BaseRetriever):
    def retrieve(self, query: str, k: int = 5, score_threshold=None, doc_type=None):
        return [
            ScoredDocument(
                document=Document(page_content="涂装车间在制车指已上线但尚未入总装车库的车辆。", metadata={"term": "涂装在制车"}),
                score=0.95,
            )
        ]


class FailingRetriever(BaseRetriever):
    def retrieve(self, query: str, k: int = 5, score_threshold=None, doc_type=None):
        raise ConnectionError("Milvus/Vector DB connection timeout")


def test_business_rag_middleware_context_api_injection_and_zero_state_pollution():
    """验证 BusinessRagMiddleware 将检索结果写入 RequestContext，不污染 State。"""
    retriever = DummyRetriever()
    mw = BusinessRagMiddleware(retriever=retriever)
    
    state: CustomState = {
        "messages": [HumanMessage(content="查询涂装在制车")],
    }
    
    req_context: RequestContext = {
        "session_id": "test_session_123",
    }
    
    class MockRuntime:
        context = req_context
        
    res = mw.before_model(state, runtime=MockRuntime())
    
    # 1. 验证返回值为空 (不向 State 回写)
    assert res is None or res == {}
    
    # 2. 验证 RequestContext 中成功注入了检索结果
    assert "rag_context" in req_context
    assert len(req_context["rag_context"]) == 1
    assert "涂装在制车" in req_context["rag_context"][0].metadata.get("term", "")
    assert req_context.get("rag_query") == "查询涂装在制车"


def test_business_rag_middleware_exception_fallback_zero_state_pollution():
    """验证 BusinessRagMiddleware 在同步检索异常时优雅回退 runtime.context，且 100% 不向 State 写入废弃字段。"""
    retriever = FailingRetriever()
    mw = BusinessRagMiddleware(retriever=retriever)
    
    state: CustomState = {
        "messages": [HumanMessage(content="查询涂装在制车")],
    }
    
    req_context: RequestContext = {
        "session_id": "test_session_fail",
        "rag_context": [],
        "lexicon_context": None,
        "rag_query": "",
    }
    
    class MockRuntime:
        context = req_context
        
    res = mw.before_model(state, runtime=MockRuntime())
    
    # 验证异常回退返回 None，0 字节写入 State
    assert res is None
    assert req_context["rag_context"] == []
    assert req_context["lexicon_context"] is None
    assert req_context["rag_query"] == "查询涂装在制车"


@pytest.mark.asyncio
async def test_business_rag_middleware_async_exception_fallback_zero_state_pollution():
    """验证 BusinessRagMiddleware 在异步检索异常时优雅回退 runtime.context，且 100% 不向 State 写入废弃字段。"""
    class FailingAsyncRetriever(BaseRetriever):
        def retrieve(self, query: str, k: int = 5, score_threshold=None, doc_type=None):
            raise ConnectionError("Timeout")
        async def aretrieve(self, query: str, k: int = 5, score_threshold=None, doc_type=None):
            raise ConnectionError("Milvus async connection timeout")

    retriever = FailingAsyncRetriever()
    mw = BusinessRagMiddleware(retriever=retriever)
    
    state: CustomState = {
        "messages": [HumanMessage(content="查询涂装在制车")],
    }
    
    req_context: RequestContext = {
        "session_id": "test_session_async_fail",
        "rag_context": [],
        "lexicon_context": None,
        "rag_query": "",
    }
    
    class MockRuntime:
        context = req_context
        
    res = await mw.abefore_model(state, runtime=MockRuntime())
    
    # 验证异步异常回退返回 None，0 字节写入 State
    assert res is None
    assert req_context["rag_context"] == []
    assert req_context["lexicon_context"] is None
    assert req_context["rag_query"] == "查询涂装在制车"


def test_checkpoint_zero_pollution_with_context_api():
    """验证使用 Context API 时，Checkpointer 保存的 channel_values 绝对不包含瞬态检索对象。"""
    checkpointer = MemorySaver()
    
    retriever = DummyRetriever()
    mw = BusinessRagMiddleware(retriever=retriever)
    
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    llm = FakeListChatModel(responses=["涂装车间在制车查询结果"])
    
    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt="You are a helpful assistant.",
        middleware=[mw],
        state_schema=CustomState,
        context_schema=RequestContext,
        checkpointer=checkpointer,
    )
    
    config = {"configurable": {"thread_id": "thread_context_test_01"}}
    req_ctx: RequestContext = {}
    
    # 执行一次调用
    agent.invoke(
        {"messages": [HumanMessage(content="查询涂装在制车")]},
        config=config,
        context=req_ctx,
    )
    
    # 检查 Checkpoint
    checkpoint = checkpointer.get(config)
    assert checkpoint is not None
    channel_values = checkpoint.get("channel_values", {})
    
    # 验证 Checkpoint 中绝对没有庞大的检索对象
    assert "rag_context" not in channel_values
    assert "lexicon_context" not in channel_values
    assert "rag_query" not in channel_values
    assert "messages" in channel_values


def test_rag_prompt_injector_reads_from_request_context():
    """验证 RagPromptInjectorMiddleware 能优先从 request.runtime.context 获取 DDL 与 RAG 文本。"""
    injector = RagPromptInjectorMiddleware()
    
    req_ctx: RequestContext = {
        "lexicon_context": {
            "formatted_text": "## 2. 数据库 Schema\nCREATE TABLE t_paint (id int, status varchar);",
        }
    }
    
    class MockRuntime:
        context = req_ctx
        
    req = ModelRequest(
        model="mock_model",
        system_message=SystemMessage(content="你是一个编排助手。"),
        messages=[HumanMessage(content="查询涂装")],
        state={},
    )
    req = req.override(runtime=MockRuntime())
    
    modified = injector._modify_request(req)
    sys_content = str(modified.system_message.content)
    
    assert "<system_rules>" in sys_content
    assert "<runtime_context>" in sys_content
    assert "CREATE TABLE t_paint" in sys_content


def test_prompt_compiler_reads_from_request_context():
    """验证 PromptCompilerMiddleware 能优先从 request.runtime.context 获取 DDL 与 RAG 文本。"""
    compiler = PromptCompilerMiddleware()
    
    req_ctx: RequestContext = {
        "lexicon_context": {
            "formatted_text": "## 2. 数据库 Schema\nCREATE TABLE t_assembly (id int, vin varchar);",
        }
    }
    
    class MockRuntime:
        context = req_ctx
        
    req = ModelRequest(
        model="mock_model",
        system_message=SystemMessage(content="你是一个 SQL 专家。"),
        messages=[HumanMessage(content="查询总装")],
        state={},
    )
    req = req.override(runtime=MockRuntime())
    
    modified = compiler._modify_request(req)
    sys_content = str(modified.system_message.content)
    
    assert "<system_rules>" in sys_content
    assert "<runtime_context>" in sys_content
    assert "CREATE TABLE t_assembly" in sys_content
