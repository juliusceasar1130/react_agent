"""RAG 检索与精排工厂方法。

根据全局 settings 创建业务检索器和可选精排器，实现上层与具体后端解耦。

支持的 RAG 后端（通过 settings.rag_backend / 环境变量 RAG_BACKEND 配置）：
  - "pgvector"       : PostgreSQL + pgvector 纯向量检索（默认）
  - "milvus_hybrid"  : LlamaIndex + Milvus 混合检索（Dense + BM25 + RRF）
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from backend.app.agent.vector.base import BaseRetriever, BaseReranker
from backend.app.agent.vector.embedding_provider import configure_llama_index_settings
from backend.app.config import settings

logger = logging.getLogger(__name__)


def _create_pgvector_retriever() -> BaseRetriever:
    """创建 PgVector 后端检索器（原有实现，不变）。"""
    from backend.app.agent.vector.pgvector.vector_store import create_business_vector_store
    from backend.app.agent.vector.pgvector.pgvector_retriever import PgVectorDocumentationRetriever

    logger.info("正在创建 PgVector 业务向量检索器 (rag_backend=pgvector)...")
    vector_store = create_business_vector_store(
        collection_name="rag_store",
        embedding_model="baai/bge-m3",
        pg_connection_string=settings.database_url,
    )
    retriever = PgVectorDocumentationRetriever(vector_store)
    logger.info("PgVectorDocumentationRetriever 初始化完成")
    return retriever


def _create_milvus_hybrid_retriever() -> BaseRetriever:
    """创建 Milvus 混合检索后端检索器（延迟初始化版本）。

    依赖 settings 中的 Milvus 相关配置：
      - milvus_uri           : Milvus 服务地址
      - milvus_collection_name: Collection 名称
      - milvus_embed_dim     : 向量维度
      - milvus_rrf_k         : RRF 融合参数
    同时需要通过 settings 读取 EMBEDDING_PROVIDER 相关配置提供本地 embedding。

    注意：
        使用延迟初始化模式，避免在模块导入时创建 Milvus 连接。
        实际连接将在首次调用 retrieve() 时建立（此时事件循环已运行）。
    """
    from backend.app.agent.vector.milvus_hybrid.milvus_retriever import MilvusHybridRetriever

    # LlamaIndex 全局 Embedding 配置（在 import 前注入，保证 Milvus 检索时使用正确模型）
    configure_llama_index_settings(settings)

    uri = getattr(settings, "milvus_uri", "http://localhost:19530")
    collection_name = getattr(settings, "milvus_collection_name", "rag_store")
    embed_dim = getattr(settings, "milvus_embed_dim", 1024)
    rrf_k = getattr(settings, "milvus_rrf_k", 60)

    logger.info(
        "正在创建 Milvus 混合检索器（延迟初始化模式）: "
        "uri=%s, collection=%s, embed_dim=%d, rrf_k=%d",
        uri, collection_name, embed_dim, rrf_k,
    )

    # 准备延迟初始化参数（不立即创建 store）
    store_params = {
        "uri": uri,
        "collection_name": collection_name,
        "embed_dim": embed_dim,
        "rrf_k": rrf_k,
        "overwrite": False,  # 工厂始终以加载模式启动，初始化由 milvus_init 脚本负责
    }

    # 使用延迟初始化模式创建检索器
    retriever = MilvusHybridRetriever(
        store_params=store_params,
        similarity_top_k=5,  # 默认值，可在 retrieve() 调用时覆盖
    )
    
    logger.info(
        "MilvusHybridRetriever（延迟初始化）准备就绪，将在首次检索时连接 Milvus"
    )
    return retriever


def create_business_retriever_and_reranker() -> Tuple[BaseRetriever, Optional[BaseReranker]]:
    """创建业务检索器与可选精排器。

    根据 settings.rag_backend 选择后端：
      - "pgvector"      -> PgVectorDocumentationRetriever
      - "milvus_hybrid" -> MilvusHybridRetriever（LlamaIndex + Milvus + BM25）

    Returns:
        (retriever, reranker)：retriever 始终非 None，reranker 在 rerank_enabled=True 时创建。
    """
    rag_backend = (getattr(settings, "rag_backend", "pgvector") or "pgvector").strip().lower()

    # ── 1. 选择检索后端 ──────────────────────────────────────────────────────────
    if rag_backend == "milvus_hybrid":
        try:
            retriever: BaseRetriever = _create_milvus_hybrid_retriever()
        except Exception as exc:
            logger.error(
                "初始化 MilvusHybridRetriever 失败，将回退为 pgvector 后端: %s", exc
            )
            retriever = _create_pgvector_retriever()
    else:
        if rag_backend != "pgvector":
            logger.warning(
                "未知的 rag_backend='%s'，将回退为 pgvector", rag_backend
            )
        retriever = _create_pgvector_retriever()

    # ── 2. 可选：创建精排器（与后端无关，始终复用 NvidiaReranker）─────────────────
    from .rerank.nvidia_reranker import NvidiaReranker

    reranker: Optional[BaseReranker] = None
    if getattr(settings, "rerank_enabled", False):
        try:
            reranker = NvidiaReranker(
                api_key=settings.nvidia_api_key,
                model=settings.rerank_model,
                top_n=settings.rerank_top_n,
                score_threshold=settings.rerank_score_threshold,
            )
            logger.info(
                "NvidiaReranker 已启用: model=%s, top_n=%s, score_threshold=%s",
                settings.rerank_model,
                settings.rerank_top_n,
                settings.rerank_score_threshold,
            )
        except Exception as exc:
            logger.warning("初始化 NvidiaReranker 失败，将使用纯检索结果: %s", exc)
            reranker = None
    else:
        logger.info("Rerank 未启用，将仅使用检索结果")

    return retriever, reranker


def add_document_to_store(
    text: str,
    metadata: dict,
) -> None:
    """将提炼后的自然语言意图和 SQL 案例写入向量库"""
    rag_backend = (getattr(settings, "rag_backend", "pgvector") or "pgvector").strip().lower()
    
    if rag_backend == "milvus_hybrid":
        from llama_index.core import Document as LlamaIndexDocument
        from backend.app.agent.vector.embedding_provider import configure_llama_index_settings
        from backend.app.agent.vector.milvus_hybrid.milvus_store import (
            create_milvus_hybrid_store,
            create_milvus_hybrid_index,
        )
        
        configure_llama_index_settings(settings)
        
        uri = getattr(settings, "milvus_uri", "http://localhost:19530")
        collection_name = getattr(settings, "milvus_collection_name", "rag_store")
        embed_dim = getattr(settings, "milvus_embed_dim", 1024)
        rrf_k = getattr(settings, "milvus_rrf_k", 60)
        
        store = create_milvus_hybrid_store(
            uri=uri,
            collection_name=collection_name,
            embed_dim=embed_dim,
            rrf_k=rrf_k,
            overwrite=False,
        )
        index = create_milvus_hybrid_index(store)
        
        doc = LlamaIndexDocument(
            text=text,
            metadata=metadata,
        )
        index.insert(doc)
        logger.info("成功插入文档到 Milvus: text=%s, metadata=%s", text[:50], metadata)
    else:
        # pgvector 后端路径
        from backend.app.agent.vector.pgvector.vector_store import create_business_vector_store
        from langchain_core.documents import Document as LangChainDocument
        
        vector_store = create_business_vector_store(
            collection_name="rag_store",
            embedding_model="baai/bge-m3",
            pg_connection_string=settings.database_url,
        )
        vector_store.add_documents([LangChainDocument(page_content=text, metadata=metadata)])
        logger.info("成功插入文档到 PgVector: text=%s, metadata=%s", text[:50], metadata)
