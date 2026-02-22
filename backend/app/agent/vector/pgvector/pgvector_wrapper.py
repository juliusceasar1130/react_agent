#!/usr/bin/env python3
# backend/app/agent/vector/pgvector/pgvector_wrapper.py
"""
基于 langchain-postgres `PGVector` 的轻量包装

只关注**查询能力**，用于在线 RAG 检索：
- 统一使用 `collection_name` 概念（与数据导入保持一致）
- 封装连接字符串的小差异
- 提供按文档类型检索等业务便捷方法
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from backend.app.agent.vector.pgvector.async_utils import ensure_windows_selector_loop

logger = logging.getLogger(__name__)


class PgVectorStoreWrapper:
    """
    基于 `PGVector` 的轻量包装，仅提供查询相关能力。

    与离线导入脚本共用同一底层结构：
    - 通过 `collection_name` 区分不同业务向量集合
    - 使用同一组表：`langchain_pg_collection` / `langchain_pg_embedding`
    """

    def __init__(
        self,
        connection_string: str,
        embedding_service: Embeddings,
        collection_name: str = "rag_store",
        **kwargs: Any,
    ) -> None:
        """
        初始化包装器

        Args:
            connection_string: PostgreSQL 连接字符串
                - 支持 `postgresql://`（会自动转换为 `postgresql+psycopg://`）
                - 也支持 `postgresql+psycopg://`（推荐，psycopg3）
            embedding_service: Embedding 模型实例
            collection_name: 逻辑集合名称（与数据导入脚本中的 collection_name 一致）
            **kwargs: 预留给 `PGVector` 的其他参数（当前基本不用）
        """
        if not connection_string:
            raise ValueError("必须提供 connection_string 参数")
        if not embedding_service:
            raise ValueError("必须提供 embedding_service 参数")

        # 在 Windows 上尽量保证事件循环兼容 psycopg3
        ensure_windows_selector_loop()

        # 为 langchain-postgres 统一连接字符串前缀
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        elif "://" not in connection_string:
            # 非标准 URL，直接拒绝，避免产生难以排查的问题
            raise ValueError(
                f"无效的连接字符串格式: {connection_string[:50]}...\n"
                "请使用 postgresql:// 或 postgresql+psycopg:// 格式"
            )

        # 使用 PGVector + collection_name（与数据导入方案保持一致）
        logger.info(f"正在初始化 PGVector，collection_name={collection_name}...")
        self._vector_store = PGVector(
            embeddings=embedding_service,
            collection_name=collection_name,
            connection=connection_string,
            **kwargs,
        )
        self.collection_name = collection_name
        logger.info(
            "PgVectorStoreWrapper 初始化成功: collection=%s", collection_name
        )

    # -------- 查询方法 --------

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """相似度搜索"""
        return self._vector_store.similarity_search(
            query=query, k=k, filter=filter, **kwargs
        )

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """
        带分数的相似度搜索

        兼容不同版本的 langchain-postgres：
        - 优先使用 `similarity_search_with_relevance_scores`
        - 回退到 `similarity_search_with_score`
        """
        store = self._vector_store

        if hasattr(store, "similarity_search_with_relevance_scores"):
            return store.similarity_search_with_relevance_scores(  # type: ignore[no-any-return]
                query=query,
                k=k,
                filter=filter,
                **kwargs,
            )

        if hasattr(store, "similarity_search_with_score"):
            return store.similarity_search_with_score(  # type: ignore[no-any-return]
                query=query,
                k=k,
                filter=filter,
                **kwargs,
            )

        # 最差情况下手动包装分数（不建议依赖）
        docs = store.similarity_search(query=query, k=k, filter=filter, **kwargs)
        # PGVector 返回已按相关性排序，但没有显式分数，这里用占位分数 0.0
        return [(doc, 0.0) for doc in docs]

    def similarity_search_by_type_with_score(
        self,
        query: str,
        doc_type: str,
        k: int = 5,
        domain: Optional[str] = None,
        score_threshold: Optional[float] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """
        按元数据中的 `type`/`domain` 检索业务文档，返回带分数的结果。

        这与导入 JSON 中的元数据结构一致：
        - metadata.type: "documentation" | "ddl" | "sql_example"
        - metadata.domain: 可选业务域

        Args:
            query: 查询文本
            doc_type: 文档类型
            k: 返回文档数量
            domain: 可选业务域
            score_threshold: 相似度分数阈值，只返回分数 >= threshold 的文档
                           None 表示不过滤。注意：分数越高表示越相似

        Returns:
            List[Tuple[Document, float]]: 文档和相似度分数的元组列表
        """
        filter_dict: Dict[str, Any] = {"type": doc_type}
        if domain:
            filter_dict["domain"] = domain

        results = self.similarity_search_with_score(
            query, k=k, filter=filter_dict, **kwargs
        )

        # 如果设置了阈值，过滤掉分数低于阈值的文档
        if score_threshold is not None:
            results = [
                (doc, score) for doc, score in results if score >= score_threshold
            ]

        return results

    # -------- 底层访问 --------

    @property
    def vector_store(self) -> PGVector:
        """访问底层 `PGVector` 实例（如需要更高级操作时使用）"""
        return self._vector_store
