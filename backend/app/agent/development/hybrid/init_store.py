"""
development/hybrid/init_store.py
===============================
【一次性初始化】混合检索索引构建模块（向量 + BM25 jieba）

职责：
  将已切分的 Node 列表写入 Milvus 混合 Collection。

使用示例：
    from development.hybrid.init_store import init_hybrid_store
    from development.data_loader import load_json_docs, split_nodes

    docs  = load_json_docs("./data/examples")
    nodes = split_nodes(docs)
    init_hybrid_store(nodes)
"""

import os
import sys
import asyncio
from typing import List

# 适配目录层级：将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config                                  # 触发模型配置
from development.data_loader import load_json_docs, split_nodes
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.vector_stores.milvus.utils import BM25BuiltInFunction

# ── 模块级默认配置 ──────────────────────────────────────────────
DEFAULT_URI = "http://localhost:19530"
DEFAULT_COLLECTION = "rag_hybrid"
DEFAULT_EMBED_DIM = 1024
DEFAULT_RRF_K = 60


def init_hybrid_store(
    nodes: List[BaseNode],
    uri: str = DEFAULT_URI,
    collection_name: str = DEFAULT_COLLECTION,
    embed_dim: int = DEFAULT_EMBED_DIM,
    overwrite: bool = True,
    rrf_k: int = DEFAULT_RRF_K,
) -> VectorStoreIndex:
    """
    【一次性】将节点写入 Milvus 混合 Collection（向量 + BM25），返回 VectorStoreIndex。
    """
    print(f"\n🚀 [hybrid/init_store] 构建混合检索索引 → Collection: {collection_name}")

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
        overwrite=overwrite,
        similarity_metric="IP",
    )

    storage_context = StorageContext.from_defaults(vector_store=hybrid_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)

    print(f"✅ [hybrid/init_store] 索引构建完成！Collection: {collection_name}")
    return index


async def main():
    print("\n🚀 [hybrid/init_store] 准备开始初始化数据 (development 模式)...")
    data_dir = "./data/examples"
    docs = load_json_docs(data_dir)
    nodes = split_nodes(docs)
    init_hybrid_store(nodes)
    print("\n✨ [hybrid/init_store] 全部操作完成。")


if __name__ == "__main__":
    asyncio.run(main())
