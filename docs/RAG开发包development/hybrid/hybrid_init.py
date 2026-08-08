"""
development/hybrid/hybrid_init.py
================================
【一次性】混合检索索引初始化入口脚本
"""

import asyncio
import os
import sys

# 适配目录层级
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config
from development.config import EMBED_DIM
from development.data_loader import load_json_docs, split_nodes
from development.hybrid.init_store import init_hybrid_store

DATA_DIR         = "./data/examples"
MILVUS_URI       = "http://localhost:19530"
COLLECTION_NAME  = "rag_hybrid"
CHUNK_SIZE       = 512
CHUNK_OVERLAP    = 50
OVERWRITE        = True
RRF_K            = 60


async def main():
    print("\n" + "=" * 60)
    print("🚀 混合检索初始化 (development 模式)")
    print("=" * 60)

    docs  = load_json_docs(DATA_DIR)
    if not docs:
        print("❌ 未找到文档，请检查：", DATA_DIR)
        return

    nodes = split_nodes(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    init_hybrid_store(nodes, uri=MILVUS_URI, collection_name=COLLECTION_NAME,
                      embed_dim=EMBED_DIM, overwrite=OVERWRITE, rrf_k=RRF_K)

    print("\n✅ 初始化完成，现在可运行 hybrid_query.py")


if __name__ == "__main__":
    asyncio.run(main())
