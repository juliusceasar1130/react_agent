"""
development/vector/init_store.py
===============================
【一次性初始化】纯向量索引构建模块

职责：
  将已切分的 Node 列表写入 Milvus 纯向量 Collection。
  此操作会调用 Embedding API 向量化所有节点并持久化，通常只需运行一次。
  后续查询直接通过 query_engine.py 加载已有 Collection，无需重复写入。

使用示例：
    from development.vector.init_store import init_vector_store
    from development.data_loader import load_json_docs, split_nodes

    docs  = load_json_docs("./data/examples")
    nodes = split_nodes(docs)
    init_vector_store(nodes)
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

# ── 模块级默认配置 ──────────────────────────────────────────────
DEFAULT_URI = "http://localhost:19530"
DEFAULT_COLLECTION = "rag_vector_only"
DEFAULT_EMBED_DIM = 1024


def init_vector_store(
    nodes: List[BaseNode],
    uri: str = DEFAULT_URI,
    collection_name: str = DEFAULT_COLLECTION,
    embed_dim: int = DEFAULT_EMBED_DIM,
    overwrite: bool = True,
) -> VectorStoreIndex:
    """
    【一次性】将节点写入 Milvus 纯向量 Collection，返回 VectorStoreIndex。
    """
    print(f"\n🛠️  [vector/init_store] 构建纯向量索引 → Collection: {collection_name}")

    vector_store = MilvusVectorStore(
        uri=uri,
        collection_name=collection_name,
        dim=embed_dim,
        overwrite=overwrite,
    )

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)

    print(f"✅ [vector/init_store] 索引构建完成！Collection: {collection_name}")
    return index


async def main():
    print("\n🛠️  [vector/init_store] 准备开始初始化数据...")
    data_dir = "./data/examples"
    docs = load_json_docs(data_dir)
    nodes = split_nodes(docs)
    init_vector_store(nodes)
    print("\n✨ [vector/init_store] 全部操作完成。")


if __name__ == "__main__":
    asyncio.run(main())
