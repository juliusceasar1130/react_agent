"""基于 PgVector 的文档检索实现。

该实现封装了现有 `PgVectorStoreWrapper`，并适配 `BaseRetriever` 抽象接口，
主要用于业务知识（documentation）类型的 RAG 检索。
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .pgvector_wrapper import PgVectorStoreWrapper
from ..base import BaseRetriever, ScoredDocument

logger = logging.getLogger(__name__)


class PgVectorDocumentationRetriever(BaseRetriever):
    """使用 PgVectorStoreWrapper 的文档检索器。

    目前主要用于 documentation 类型文档的检索，预留 doc_type / domain 参数以便后续扩展。
    """

    def __init__(self, vector_store: PgVectorStoreWrapper) -> None:
        """
        Args:
            vector_store: 已初始化好的 PgVectorStoreWrapper 实例。
        """
        self._vector_store = vector_store

    def retrieve(
        self,
        query: str,
        k: int = 5,
        score_threshold: Optional[float] = None,
        doc_type: str = "documentation",
        domain: Optional[str] = None,
    ) -> List[ScoredDocument]:
        if not query or not query.strip():
            logger.warning("PgVectorDocumentationRetriever: 查询为空，返回空结果")
            return []

        # 当前实现仅支持 documentation 类型，其它类型预留扩展
        if doc_type.lower() != "documentation":
            logger.info(
                "PgVectorDocumentationRetriever: 当前仅支持 documentation 类型，"
                "doc_type=%s 将按 documentation 处理",
                doc_type,
            )

        try:
            # PgVectorStoreWrapper 目前假定内部已经按业务维度划分集合，
            # 因此这里的 domain 先作为 future 参数预留，不做过滤。
            logger.info(
                "PgVectorDocumentationRetriever: 开始检索, query='%s', k=%d, "
                "score_threshold=%s, domain=%s",
                query[:80],
                k,
                score_threshold,
                domain,
            )

            # 使用 PgVectorStoreWrapper 的带分数检索能力，并按文档类型 / 业务域过滤
            # 这里直接复用 wrapper 中对不同 PGVector 版本的适配逻辑
            results = self._vector_store.similarity_search_by_type_with_score(
                query=query,
                doc_type="documentation",
                k=k,
                domain=domain,
                score_threshold=score_threshold,
            )

            scored: List[ScoredDocument] = [
                ScoredDocument(document=doc, score=float(score or 0.0))
                for doc, score in results
            ]

            # 保险起见再次按分数降序排序（wrapper 已大概率排序，但这里不依赖其实现）
            scored.sort(key=lambda x: x.score, reverse=True)

            if scored:
                scores = [s.score for s in scored]
                logger.info(
                    "PgVectorDocumentationRetriever: 检索完成, 命中=%d, "
                    "score_range=[%.4f, %.4f]",
                    len(scored),
                    min(scores),
                    max(scores),
                )
            else:
                logger.info("PgVectorDocumentationRetriever: 检索完成, 未命中文档")

            return scored
        except Exception as exc:  # 防御性，避免检索错误影响整体 Agent
            logger.error(
                "PgVectorDocumentationRetriever: 检索过程中发生异常，将返回空结果: %s",
                exc,
            )
            return []
