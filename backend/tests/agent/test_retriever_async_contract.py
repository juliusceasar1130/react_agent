# backend/tests/agent/test_retriever_async_contract.py
"""
RAG 检索器异步接口契约测试。

背景：Phase 1 整改中 rag_middleware.abefore_model 调用 self.retriever.aretrieve(...)，
但 MilvusHybridRetriever 从未实现该方法，导致异步路径 AttributeError、
RAG 双通道（业务知识 + 词典）被异常回退置空。

本测试验证：
1. BaseRetriever 基类默认 aretrieve（asyncio.to_thread 包装同步 retrieve）的委托语义
2. 所有 BaseRetriever 子类实例均具备兼容签名的 aretrieve（防止接口缺口回归）
"""
import inspect

import pytest
from langchain_core.documents import Document

from backend.app.agent.vector.base import BaseRetriever, ScoredDocument


class _StubRetriever(BaseRetriever):
    """仅实现同步 retrieve 的最小子类，用于验证基类默认 aretrieve 委托。"""

    def __init__(self, results):
        self._results = results
        self.called_kwargs = None

    def retrieve(self, query, k=5, score_threshold=None, doc_type="documentation", domain=None):
        self.called_kwargs = {
            "query": query,
            "k": k,
            "score_threshold": score_threshold,
            "doc_type": doc_type,
            "domain": domain,
        }
        return self._results


@pytest.mark.asyncio
async def test_base_retriever_default_aretrieve_delegates_to_retrieve():
    """基类默认 aretrieve 应通过线程池委托同步 retrieve 并透传全部参数。"""
    docs = [ScoredDocument(document=Document(page_content="测试文档"), score=0.9)]
    stub = _StubRetriever(results=docs)

    result = await stub.aretrieve(
        query="涂装在制车",
        k=3,
        score_threshold=0.5,
        doc_type="documentation",
        domain="manufacturing",
    )

    assert result == docs
    assert stub.called_kwargs == {
        "query": "涂装在制车",
        "k": 3,
        "score_threshold": 0.5,
        "doc_type": "documentation",
        "domain": "manufacturing",
    }


@pytest.mark.asyncio
async def test_base_retriever_aretrieve_passes_through_defaults():
    """默认参数（k=5, score_threshold=None 等）应与同步 retrieve 一致透传。"""
    stub = _StubRetriever(results=[])

    await stub.aretrieve(query="默认参数")

    assert stub.called_kwargs == {
        "query": "默认参数",
        "k": 5,
        "score_threshold": None,
        "doc_type": "documentation",
        "domain": None,
    }


def test_milvus_hybrid_retriever_has_aretrieve():
    """真实 MilvusHybridRetriever 必须具备兼容签名的 aretrieve（修复回归的靶点）。"""
    from backend.app.agent.vector.milvus_hybrid.milvus_retriever import MilvusHybridRetriever

    # 延迟初始化模式：仅保存参数不建立连接，避免测试依赖真实 Milvus
    retriever = MilvusHybridRetriever(
        store_params={
            "uri": "http://127.0.0.1:19530",
            "collection_name": "rag_store",
            "embed_dim": 1024,
            "rrf_k": 60,
        }
    )
    assert hasattr(retriever, "aretrieve")
    sig = inspect.signature(retriever.aretrieve)
    assert "query" in sig.parameters
    assert "k" in sig.parameters
    assert "doc_type" in sig.parameters


def test_pgvector_retriever_has_aretrieve():
    """真实 PgVectorDocumentationRetriever 同样应具备兼容签名的 aretrieve。"""
    from backend.app.agent.vector.pgvector.pgvector_retriever import PgVectorDocumentationRetriever

    # vector_store 仅被保存为引用，构造时不触发任何连接
    retriever = PgVectorDocumentationRetriever(vector_store=None)
    assert hasattr(retriever, "aretrieve")
    sig = inspect.signature(retriever.aretrieve)
    assert "query" in sig.parameters
    assert "k" in sig.parameters
    assert "doc_type" in sig.parameters
