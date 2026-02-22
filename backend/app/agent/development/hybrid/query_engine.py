"""
development/hybrid/query_engine.py
==================================
【复用】混合检索引擎加载与查询模块（向量 + BM25 jieba）

使用示例：
    from development.hybrid.query_engine import get_engine, run_query

    engine = get_engine()
    run_query(engine, "RB是什么")
"""

import os
import sys
import asyncio
import time
from typing import Tuple

# 适配目录层级：将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config                                  # 触发模型配置
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.vector_stores.milvus.utils import BM25BuiltInFunction

# ── 模块级默认配置 ──────────────────────────────────────────────
DEFAULT_URI = "http://localhost:19530"
DEFAULT_COLLECTION = "rag_hybrid"
DEFAULT_EMBED_DIM = 1024
DEFAULT_RRF_K = 60


def get_engine(
    uri: str = DEFAULT_URI,
    collection_name: str = DEFAULT_COLLECTION,
    embed_dim: int = DEFAULT_EMBED_DIM,
    similarity_top_k: int = 5,
    rrf_k: int = DEFAULT_RRF_K,
) -> RetrieverQueryEngine:
    """
    加载混合 QueryEngine。
    """
    print(f"🔗 [hybrid/query_engine] 加载引擎 ← Collection: {collection_name}")

    bm25_function = BM25BuiltInFunction(
        analyzer_params={
            "tokenizer": "jieba",
            "filter": ["cnalphanumonly"],
        },
    )

    hybrid_store = MilvusVectorStore(
        uri=uri,
        collection_name=collection_name,
        dim=embed_dim,
        enable_sparse=True,
        sparse_embedding_function=bm25_function,
        hybrid_ranker="RRFRanker",
        hybrid_ranker_params={"k": rrf_k},
        overwrite=False,
        similarity_metric="IP",
    )

    storage_context = StorageContext.from_defaults(vector_store=hybrid_store)
    index = VectorStoreIndex.from_vector_store(
        vector_store=hybrid_store,
        storage_context=storage_context,
    )

    engine = index.as_query_engine(
        vector_store_query_mode="hybrid",
        similarity_top_k=similarity_top_k,
    )
    print(f"✅ [hybrid/query_engine] 引擎就绪！")
    return engine


def run_query(
    engine,
    query_str: str,
    top_n_display: int = 3,
) -> Tuple[float, float, float]:
    """
    执行完整 RAG 查询。
    """
    print(f"\n{'=' * 60}")
    print(f"🔍 [混合检索] 查询：{query_str}")
    print("-" * 60)

    t0 = time.time()
    nodes = engine.retrieve(query_str)
    elapsed_retrieve = time.time() - t0

    print(f"⏱  检索耗时：{elapsed_retrieve:.2f}s")
    _print_source_nodes(nodes, top_n=top_n_display)

    t1 = time.time()
    response = engine.synthesize(query_str, nodes)
    elapsed_llm = time.time() - t1

    print(f"⏱  LLM 生成耗时：{elapsed_llm:.2f}s  |  总耗时：{elapsed_retrieve + elapsed_llm:.2f}s")
    print("\n💬 回答：\n", response)

    return elapsed_retrieve, elapsed_llm, elapsed_retrieve + elapsed_llm


def _print_source_nodes(nodes, top_n: int = 3) -> None:
    for i, node in enumerate(nodes[:top_n], 1):
        score = node.score
        score_str = f"{score:.4f}" if isinstance(score, float) else str(score)
        snippet = node.get_content().strip().replace("\n", " ")[:120]
        print(f"  [{i}] Score={score_str} | {snippet}...")


async def main():
    print("\n⚡ [hybrid/query_engine] 准备开始查询 (development 模式)...")
    engine = get_engine()
    test_queries = ["RB是什么"]
    for q in test_queries:
        run_query(engine, q)
    print("\n✨ [hybrid/query_engine] 查询测试完成。")


if __name__ == "__main__":
    asyncio.run(main())
