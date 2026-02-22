"""
milvus_init/example_usage.py
=============================
使用示例脚本

展示如何使用 milvus_init 模块的几种方式。
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 方式1: 使用主函数（推荐）
from app.agent.vector.milvus_init.init_milvus import main


async def example_1_basic_usage():
    """示例1: 基本使用（使用配置文件中的默认值）"""
    print("\n" + "=" * 70)
    print("示例1: 基本使用")
    print("=" * 70)
    await main()


async def example_2_custom_params():
    """示例2: 自定义参数"""
    print("\n" + "=" * 70)
    print("示例2: 自定义参数")
    print("=" * 70)
    await main(
        data_dir="./data/examples",
        collection_name="my_custom_collection",
        chunk_size=1024,
        chunk_overlap=100,
        overwrite=True,
        rrf_k=80
    )


async def example_3_step_by_step():
    """示例3: 分步骤使用（更灵活的控制）"""
    print("\n" + "=" * 70)
    print("示例3: 分步骤使用")
    print("=" * 70)
    
    from app.agent.vector.milvus_init.data_loader import load_json_docs, split_nodes
    from app.agent.vector.milvus_init.init_store import init_hybrid_store
    from app.config import settings
    
    # 步骤1: 加载文档
    print("\n步骤1: 加载文档...")
    docs = load_json_docs("./data/examples")
    if not docs:
        print("❌ 未找到文档")
        return
    
    # 步骤2: 切分节点
    print("\n步骤2: 切分节点...")
    nodes = split_nodes(docs, chunk_size=512, chunk_overlap=50)
    
    # 步骤3: 构建索引
    print("\n步骤3: 构建索引...")
    index = init_hybrid_store(
        nodes=nodes,
        uri=settings.milvus_uri,
        collection_name=settings.milvus_collection_name,
        embed_dim=settings.milvus_embed_dim,
        overwrite=True,
        rrf_k=settings.milvus_rrf_k
    )
    
    print(f"\n✅ 完成！索引包含 {len(nodes)} 个节点")


if __name__ == "__main__":
    # 选择要运行的示例
    # 取消注释你想要运行的示例
    
    # 示例1: 基本使用
    asyncio.run(example_1_basic_usage())
    
    # 示例2: 自定义参数
    # asyncio.run(example_2_custom_params())
    
    # 示例3: 分步骤使用
    # asyncio.run(example_3_step_by_step())
