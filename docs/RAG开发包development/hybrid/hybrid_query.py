"""
development/hybrid/hybrid_query.py
=================================
【复用】混合检索查询入口脚本
"""

import asyncio
import os
import sys

# 适配目录层级
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config
from development.config import EMBED_DIM
from development.hybrid.query_engine import get_engine, run_query

MILVUS_URI       = "http://localhost:19530"
COLLECTION_NAME  = "rag_hybrid"
SIMILARITY_TOP_K = 5
RRF_K            = 60

QUERIES = [
    "RB是什么",
]


async def main():
    print("\n" + "=" * 60)
    print("⚡ 混合检索查询 (development 模式)")
    print("=" * 60)

    engine = get_engine(
        uri=MILVUS_URI,
        collection_name=COLLECTION_NAME,
        embed_dim=EMBED_DIM,
        similarity_top_k=SIMILARITY_TOP_K,
        rrf_k=RRF_K,
    )

    for q in QUERIES:
        run_query(engine, q)

    print("\n✨ 查询完成！")


if __name__ == "__main__":
    asyncio.run(main())
