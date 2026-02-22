# backend/app/agent/utils/rerank_service.py
"""
NVIDIA NIM Rerank 服务封装

提供基于 NVIDIA NIM API 的文档重排序功能，用于 RAG 管道中的精排层。
支持降级策略：API 调用失败时自动回退到原始排序。
"""

import logging
from typing import Any, Dict, List, Optional

import requests
from langchain_core.documents import Document

from backend.app.agent.vector.base import BaseReranker, ScoredDocument

logger = logging.getLogger(__name__)

# NVIDIA NIM Rerank API 端点
NVIDIA_RERANK_ENDPOINT = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"


class NvidiaRerankService(BaseReranker):
    """
    NVIDIA NIM Rerank 服务

    使用 NVIDIA NIM 的 rerank-qa-mistral-4b 模型对向量检索结果进行精排。
    
    特性：
    - 支持 LangChain Document 对象
    - 异常时自动降级（返回原始列表）
    - 支持 score_threshold 阈值过滤
    - 支持自定义 top_n 截断
    """

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/rerank-qa-mistral-4b",
        top_n: int = 3,
        score_threshold: Optional[float] = None,
        timeout: int = 10,
    ) -> None:
        """
        Args:
            api_key: NVIDIA API Key
            model: Rerank 模型名称
            top_n: 保留的 Top-N 结果数量
            score_threshold: Rerank 分数阈值，只返回分数 >= threshold 的文档。
                           None 表示不做阈值过滤
            timeout: API 请求超时秒数
        """
        if not api_key:
            raise ValueError("NVIDIA API Key 不能为空")
        
        self.api_key = api_key
        self.model = model
        self.top_n = top_n
        self.score_threshold = score_threshold
        self.timeout = timeout

        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info(
            f"NvidiaRerankService 初始化: model={model}, "
            f"top_n={top_n}, score_threshold={score_threshold}"
        )

    def _extract_text(self, doc: Document) -> str:
        """从 LangChain Document 中提取文本"""
        return doc.page_content if doc.page_content else ""

    def rerank(
        self,
        query: str,
        documents: List[Document],
    ) -> List[ScoredDocument]:
        """
        调用 NVIDIA Rerank API 对文档列表重排序

        Args:
            query: 用户查询
            documents: 候选文档列表 (LangChain Document)

        Returns:
            按 Rerank 分数降序排列的 (Document, score) 列表。
            如果 API 调用失败，返回原始列表（分数为 0.0）作为降级。
        """
        if not documents:
            return []

        if not query or not query.strip():
            logger.warning("Rerank: 查询为空，跳过重排序")
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]

        # 提取文本内容
        passages = [self._extract_text(doc) for doc in documents]

        # 过滤空文本（NVIDIA API 不接受空段落）
        valid_indices = [i for i, p in enumerate(passages) if p.strip()]
        if not valid_indices:
            logger.warning("Rerank: 所有文档文本为空，跳过重排序")
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]

        valid_passages = [passages[i] for i in valid_indices]
        valid_documents = [documents[i] for i in valid_indices]

        # 构建 NVIDIA NIM 请求体
        payload: Dict[str, Any] = {
            "model": self.model,
            "query": {"text": query},
            "passages": [{"text": p} for p in valid_passages],
        }

        try:
            logger.info(
                f"Rerank 请求: query='{query[:50]}...', "
                f"文档数={len(valid_passages)}"
            )

            response = requests.post(
                NVIDIA_RERANK_ENDPOINT,
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()

        except requests.exceptions.Timeout:
            logger.warning(
                "Rerank API 超时 (%ss)，降级使用原始排序", self.timeout
            )
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]
        except requests.exceptions.RequestException as e:
            logger.warning("Rerank API 请求失败，降级使用原始排序: %s", e)
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]
        except Exception as e:
            logger.error("Rerank 解析响应失败，降级使用原始排序: %s", e)
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]

        # 解析响应并排序
        rankings = result.get("rankings", [])
        if not rankings:
            logger.warning("Rerank API 返回空 rankings，降级使用原始排序")
            return [ScoredDocument(document=doc, score=0.0) for doc in documents]

        # 按 logit 分数降序排列
        ranked_results: List[ScoredDocument] = []
        for item in sorted(rankings, key=lambda x: x.get("logit", 0.0), reverse=True):
            idx = item.get("index", -1)
            score_raw = item.get("logit", 0.0)
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0

            if 0 <= idx < len(valid_documents):
                ranked_results.append(
                    ScoredDocument(document=valid_documents[idx], score=score)
                )

        # 记录重排序结果
        for i, item in enumerate(ranked_results):
            doc = item.document
            score = item.score
            meta = getattr(doc, "metadata", {}) or {}
            term = meta.get("term", meta.get("title", f"doc#{i}"))
            logger.info("  Rerank #%d: score=%.4f, term='%s'", i + 1, score, term)

        # 阈值过滤
        if self.score_threshold is not None:
            before_count = len(ranked_results)
            ranked_results = [
                item for item in ranked_results if item.score >= self.score_threshold
            ]
            logger.info(
                "Rerank 阈值过滤: threshold=%s, 过滤前=%d, 过滤后=%d",
                self.score_threshold,
                before_count,
                len(ranked_results),
            )

        # Top-N 截断
        if self.top_n is not None and len(ranked_results) > self.top_n:
            ranked_results = ranked_results[: self.top_n]
            logger.info("Rerank Top-N 截断: 保留前 %d 条", self.top_n)

        logger.info("Rerank 完成: 最终保留 %d 条文档", len(ranked_results))
        return ranked_results
