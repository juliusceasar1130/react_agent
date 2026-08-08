"""
development/vector/vector_init.py
===============================
【一次性】纯向量索引初始化入口脚本

功能：加载 JSON 数据 → 切分节点 → 写入 Milvus 纯向量 Collection
运行：python vector_init.py
"""

import asyncio
import os
import sys

# 适配目录层级：将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import development.config                           # 触发模型配置
from development.config import EMBED_DIM
from development.data_loader import load_json_docs, split_nodes
from development.vector.init_store import init_vector_store

DATA_DIR         = "./data/examples"
MILVUS_URI       = "http://localhost:19530"
COLLECTION_NAME  = "rag_vector_only"
CHUNK_SIZE       = 512
CHUNK_OVERLAP    = 50
OVERWRITE        = True                        # 首次运行建议 True


async def main():
    print("\n" + "=" * 60)
    print("🛠️  纯向量索引初始化 (development 模式)")
    print("=" * 60)

    docs  = load_json_docs(DATA_DIR)
    if not docs:
        print("❌ 未找到文档，请检查：", DATA_DIR)
        return

    nodes = split_nodes(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    init_vector_store(nodes, uri=MILVUS_URI, collection_name=COLLECTION_NAME,
                      embed_dim=EMBED_DIM, overwrite=OVERWRITE)

    print("\n✅ 初始化完成，现在可运行 vector_query.py")


if __name__ == "__main__":
    asyncio.run(main())
