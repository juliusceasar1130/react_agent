"""
milvus_init/init_milvus.py
==========================
【一次性】Milvus 混合检索索引初始化入口脚本

功能：
  1. 从指定目录加载 JSON 数据文件
  2. 将文档切分为节点
  3. 构建 Milvus 混合检索索引（向量 + BM25）

运行方式（必须在 backend 的父目录执行）：
  cd .tree/features/agent
  python -m backend.app.agent.vector.milvus_init.init_milvus

  或作为模块导入：
  from backend.app.agent.vector.milvus_init.init_milvus import main
  import asyncio
  asyncio.run(main())
"""

import os
import sys
from pathlib import Path

# 确保 backend 包可被导入：将 backend 的父目录加入 sys.path
# 项目使用 backend.app 作为包前缀，需从 .tree/features/agent 运行
_backend_dir = Path(__file__).resolve().parent.parent.parent.parent
_project_root = _backend_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from backend.app.config import settings
from backend.app.agent.vector.milvus_init.data_loader import load_json_docs, split_nodes
from backend.app.agent.vector.milvus_init.init_store import init_hybrid_store


async def main(
    data_dir: str = None,
    milvus_uri: str = None,
    collection_name: str = None,
    embed_dim: int = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
    overwrite: bool = None,
    rrf_k: int = None,
):
    """
    初始化 Milvus 混合检索索引的主函数。

    Args:
        data_dir: 数据目录路径（默认从配置读取）
        milvus_uri: Milvus 服务地址（默认从配置读取）
        collection_name: Collection 名称（默认从配置读取）
        embed_dim: 向量维度（默认从配置读取）
        chunk_size: 分块大小（默认从配置读取）
        chunk_overlap: 分块重叠大小（默认从配置读取）
        overwrite: 是否覆盖已有 Collection（默认从配置读取）
        rrf_k: RRF 融合参数（默认从配置读取）
    """
    print("\n" + "=" * 70)
    print("🚀 Milvus 混合检索索引初始化")
    print("=" * 70)

    # 从配置或参数中获取设置
    data_dir = data_dir or settings.milvus_data_dir
    milvus_uri = milvus_uri or settings.milvus_uri
    collection_name = collection_name or settings.milvus_collection_name
    embed_dim = embed_dim or settings.milvus_embed_dim
    chunk_size = chunk_size or settings.milvus_chunk_size
    chunk_overlap = chunk_overlap or settings.milvus_chunk_overlap
    overwrite = overwrite if overwrite is not None else settings.milvus_overwrite
    rrf_k = rrf_k or settings.milvus_rrf_k

    # 打印配置信息
    print(f"\n📋 配置信息:")
    print(f"  数据目录: {data_dir}")
    print(f"  Milvus URI: {milvus_uri}")
    print(f"  Collection 名称: {collection_name}")
    print(f"  向量维度: {embed_dim}")
    print(f"  分块大小: {chunk_size}")
    print(f"  分块重叠: {chunk_overlap}")
    print(f"  覆盖模式: {overwrite}")
    print(f"  RRF K 值: {rrf_k}")

    # 检查数据目录
    if not os.path.exists(data_dir):
        print(f"\n❌ 错误: 数据目录不存在: {data_dir}")
        print(f"   请检查配置或创建数据目录")
        return

    # 步骤1: 加载 JSON 文档
    print(f"\n📂 步骤 1/3: 加载 JSON 文档...")
    docs = load_json_docs(data_dir)
    if not docs:
        print(f"\n❌ 错误: 在 {data_dir} 下未找到任何 JSON 文件")
        print(f"   请确保数据目录中包含 JSON 格式的文档文件")
        return

    # 步骤2: 切分文档为节点
    print(f"\n✂️  步骤 2/3: 切分文档为节点...")
    nodes = split_nodes(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not nodes:
        print(f"\n❌ 错误: 未能生成任何节点")
        return

    # 步骤3: 初始化 Milvus 混合索引
    print(f"\n🔨 步骤 3/3: 构建 Milvus 混合检索索引...")
    try:
        index = init_hybrid_store(
            nodes=nodes,
            uri=milvus_uri,
            collection_name=collection_name,
            embed_dim=embed_dim,
            overwrite=overwrite,
            rrf_k=rrf_k,
        )
        print(f"\n✅ 初始化完成！")
        print(f"   Collection: {collection_name}")
        print(f"   节点数量: {len(nodes)}")
        print(f"\n💡 提示: 现在可以使用 RAG 查询功能了")
    except Exception as e:
        print(f"\n❌ 初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
