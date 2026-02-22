"""
milvus_init/init_store.py
=========================
【一次性初始化】混合检索索引构建模块（向量 + BM25 jieba）

职责：
  将已切分的 Node 列表写入 Milvus 混合 Collection。

使用示例：
    from backend.app.agent.vector.milvus_init.init_store import init_hybrid_store
    from backend.app.agent.vector.milvus_init.data_loader import load_json_docs, split_nodes

    docs  = load_json_docs("./data/examples")
    nodes = split_nodes(docs)
    init_hybrid_store(nodes)
"""

from typing import List

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import BaseNode
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.vector_stores.milvus.utils import BM25BuiltInFunction


def _configure_llama_index_settings() -> None:
    """
    配置 LlamaIndex 全局 Settings（Embedding 模型）。
    
    使用 NVIDIA NV-EmbedQA-E5-V5（dim=1024），与 Milvus 配置保持一致。
    此函数幂等，多次调用无副作用。
    """
    from llama_index.core import Settings as LISettings
    from llama_index.embeddings.nvidia import NVIDIAEmbedding
    from backend.app.config import settings
    import os

    api_key = getattr(settings, "nvidia_api_key", "") or os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        raise ValueError("缺少 NVIDIA_API_KEY，请检查 .env 文件或环境变量")

    LISettings.embed_model = NVIDIAEmbedding(
        model="nvidia/nv-embedqa-e5-v5",
        api_key=api_key,
    )
    print("  ✅ [init_store] LlamaIndex Embedding 已配置: nvidia/nv-embedqa-e5-v5")


def init_hybrid_store(
    nodes: List[BaseNode],
    uri: str,
    collection_name: str,
    embed_dim: int,
    overwrite: bool = True,
    rrf_k: int = 60,
) -> VectorStoreIndex:
    """
    【一次性】将节点写入 Milvus 混合 Collection（向量 + BM25），返回 VectorStoreIndex。

    Args:
        nodes: 已切分的 Node 列表
        uri: Milvus 服务地址
        collection_name: Collection 名称
        embed_dim: 向量维度
        overwrite: 是否覆盖已有 Collection
        rrf_k: RRF 融合参数

    Returns:
        VectorStoreIndex 对象
    """
    print(f"\n🚀 [init_store] 构建混合检索索引 → Collection: {collection_name}")

    # 配置 LlamaIndex Settings（确保 Embedding 模型正确）
    _configure_llama_index_settings()

    # 配置 BM25 分词器（使用 jieba）
    bm25_function = BM25BuiltInFunction(
        analyzer_params={
            "tokenizer": "jieba",
            "filter": ["cnalphanumonly"],
        },
    )

    # 创建 Milvus 混合向量存储
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

    # 构建索引
    storage_context = StorageContext.from_defaults(vector_store=hybrid_store)
    index = VectorStoreIndex(nodes, storage_context=storage_context)

    print(f"✅ [init_store] 索引构建完成！Collection: {collection_name}")
    return index
