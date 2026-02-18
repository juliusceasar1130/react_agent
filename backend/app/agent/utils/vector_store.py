#!/usr/bin/env python3
# backend/app/agent/utils/vector_store.py
"""
向量存储工具函数

提供业务知识向量库的创建和配置。
使用 `PGVector`（PostgreSQL + pgvector 扩展）作为唯一后端。
"""

import os
import logging
from typing import Optional

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from backend.app.agent.utils.async_utils import ensure_windows_selector_loop
from backend.app.agent.utils.pgvector_wrapper import PgVectorStoreWrapper
from backend.app.config import settings

logger = logging.getLogger(__name__)

# 在模块加载时确保事件循环策略正确设置
ensure_windows_selector_loop()


def _get_nvidia_api_key() -> str:
    """
    统一获取 NVIDIA API Key：优先使用 settings，其次使用环境变量。
    """
    api_key = getattr(settings, "nvidia_api_key", None) or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError(
            "NVIDIA_API_KEY 未设置，无法创建向量库或 Embedding 服务。\n"
            "请在配置或环境变量中设置 NVIDIA_API_KEY"
        )
    return api_key


def create_business_vector_store(
    collection_name: str = "rag_store",
    pg_connection_string: Optional[str] = None,
    embedding_model: str = "baai/bge-m3",
) -> PgVectorStoreWrapper:
    """
    创建业务知识向量库实例（基于 `PGVector` 的轻量包装）。

    Args:
        collection_name: 业务向量集合名称，需与数据导入脚本中的 collection_name 保持一致。
                         默认值为 "rag_store"（与导入 CLI 保持一致）。
        pg_connection_string: PostgreSQL 连接字符串。
                            如果未提供，将优先使用 settings.database_url，
                            否则使用环境变量 DATABASE_URL。
        embedding_model: NVIDIA Embedding 模型名称，默认为 "baai/bge-m3"。

    Returns:
        PgVectorStoreWrapper 实例。

    Raises:
        ValueError: 如果配置无效。
    """
    # 获取 NVIDIA API Key（优先使用 settings，其次使用环境变量)
    nvidia_api_key = _get_nvidia_api_key()
    logger.info(f"已获取 NVIDIA API Key，正在初始化 Embedding 模型: {embedding_model}...")

    # 初始化 Embedding 模型
    embeddings = NVIDIAEmbeddings(
        model=embedding_model,
        api_key=nvidia_api_key,
    )
    logger.info(f"Embedding 模型初始化成功")

    # 使用 PGVector 后端
    if not pg_connection_string:
        # 优先使用 settings.database_url，其次使用环境变量
        pg_connection_string = getattr(settings, "database_url", None) or os.getenv(
            "DATABASE_URL"
        )
        if not pg_connection_string:
            raise ValueError(
                "必须提供 pg_connection_string 参数，"
                "或配置 settings.database_url，"
                "或设置 DATABASE_URL 环境变量"
            )

    logger.info(f"正在创建 PgVectorStoreWrapper，collection_name={collection_name}...")
    vector_store = PgVectorStoreWrapper(
        connection_string=pg_connection_string,
        embedding_service=embeddings,
        collection_name=collection_name,
    )
    logger.info(
        "业务知识向量库已创建 (PGVector + NVIDIA Embeddings): "
        "collection=%s, model=%s",
        collection_name,
        embedding_model,
    )

    return vector_store


def get_embedding_service(
    embedding_model: str = "baai/bge-m3",
) -> NVIDIAEmbeddings:
    """
    获取 Embedding 服务实例。

    Args:
        embedding_model: NVIDIA Embedding 模型名称，默认为 "baai/bge-m3"。

    Returns:
        NVIDIAEmbeddings 实例。

    Raises:
        ValueError: 如果配置无效。
    """
    nvidia_api_key = _get_nvidia_api_key()

    embeddings = NVIDIAEmbeddings(
        model=embedding_model,
        api_key=nvidia_api_key,
    )

    logger.info("Embedding 服务已创建: model=%s", embedding_model)

    return embeddings