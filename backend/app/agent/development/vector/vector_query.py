"""
development/vector/vector_query.py
================================
【复用】纯向量检索查询入口脚本

功能：从已有 Milvus 纯向量 Collection 加载引擎并执行查询
运行：python vector_query.py
"""

import asyncio
import os
import sys

# 适配目录层级：将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config                           # 触发模型配置
from development.config import EMBED_DIM
from development.vector.query_engine import get_engine, run_query

MILVUS_URI       = "http://localhost:19530"
COLLECTION_NAME  = "rag_vector_only"
SIMILARITY_TOP_K = 5

QUERIES = [
    "RB是什么",
]


async def main():
    print("\n" + "=" * 60)
    print("🔍 纯向量检索查询 (development 模式)")
    print("=" * 60)

    engine = get_engine(
        uri=MILVUS_URI,
        collection_name=COLLECTION_NAME,
        embed_dim=EMBED_DIM,
        similarity_top_k=SIMILARITY_TOP_K,
    )

    for q in QUERIES:
        run_query(engine, q)

    print("\n✨ 查询完成！")


if __name__ == "__main__":
    asyncio.run(main())
