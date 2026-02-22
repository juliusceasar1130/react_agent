"""Milvus 混合检索向量库封装。

负责创建和加载 MilvusVectorStore（含 BM25 稀疏向量索引），
供 MilvusHybridRetriever 使用。

主要函数:
  - create_milvus_hybrid_store: 创建/加载 MilvusVectorStore 实例
  - create_milvus_hybrid_index: 在已有 store 上建立 VectorStoreIndex
"""

from __future__ import annotations

import logging
from typing import Optional

from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.vector_stores.milvus.utils import BM25BuiltInFunction
from llama_index.core import VectorStoreIndex, StorageContext

logger = logging.getLogger(__name__)


def _build_bm25_function() -> BM25BuiltInFunction:
    """构建中文 BM25 分词函数（jieba）。"""
    return BM25BuiltInFunction(
        analyzer_params={
            "tokenizer": "jieba",          # 中文分词
            "filter": ["cnalphanumonly"],   # 保留中文字母数字
        },
    )


def create_milvus_hybrid_store(
    uri: str = "http://localhost:19530",
    collection_name: str = "rag_store",
    embed_dim: int = 1024,
    rrf_k: int = 60,
    overwrite: bool = False,
) -> MilvusVectorStore:
    """创建或加载 Milvus 混合检索向量库。

    Args:
        uri: Milvus 服务地址，默认 http://localhost:19530。
        collection_name: Milvus Collection 名称，默认 rag_store。
        embed_dim: 向量维度，需与 Embedding 模型一致，默认 1024（NVIDIA nv-embedqa-e5-v5）。
        rrf_k: RRF 融合参数，越大结果越均衡，默认 60。
        overwrite: 是否清空并重建 Collection，默认 False（加载已有 Collection）。

    Returns:
        初始化完成的 MilvusVectorStore 实例。

    Raises:
        ImportError: 若未安装 llama-index-vector-stores-milvus。
        Exception: Milvus 连接或 Collection 操作失败时透传异常。
    """
    logger.info(
        "正在%s Milvus 混合检索 Collection: uri=%s, collection=%s, overwrite=%s",
        "重建" if overwrite else "连接",
        uri,
        collection_name,
        overwrite,
    )

    bm25_function = _build_bm25_function()

    store = MilvusVectorStore(
        uri=uri,
        collection_name=collection_name,
        dim=embed_dim,
        enable_sparse=True,                           # 开启稀疏向量（BM25）
        sparse_embedding_function=bm25_function,
        hybrid_ranker="RRFRanker",                    # 倒数排名融合
        hybrid_ranker_params={"k": rrf_k},
        overwrite=overwrite,
        similarity_metric="IP",                       # 混合模式必须使用 InnerProduct
    )

    logger.info(
        "Milvus 混合检索 Store 就绪: collection=%s, embed_dim=%d, rrf_k=%d",
        collection_name,
        embed_dim,
        rrf_k,
    )
    return store


def create_milvus_hybrid_index(
    store: MilvusVectorStore,
) -> VectorStoreIndex:
    """在已有 MilvusVectorStore 上创建 VectorStoreIndex（仅加载模式）。

    Args:
        store: 由 create_milvus_hybrid_store 返回的 MilvusVectorStore。

    Returns:
        VectorStoreIndex 实例，可通过 .as_retriever() 或 .as_query_engine() 使用。
    """
    storage_context = StorageContext.from_defaults(vector_store=store)
    index = VectorStoreIndex.from_vector_store(
        vector_store=store,
        storage_context=storage_context,
    )
    logger.info("VectorStoreIndex 加载完成，基于 Milvus 混合 Collection")
    return index
