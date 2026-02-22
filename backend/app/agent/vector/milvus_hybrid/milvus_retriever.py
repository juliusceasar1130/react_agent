"""基于 LlamaIndex + Milvus 的混合检索器。

实现 BaseRetriever 抽象接口，内部使用 LlamaIndex hybrid 检索模式
（稠密向量 + BM25 稀疏向量 + RRF 融合），将检索结果转换为
与 BusinessRagMiddleware 兼容的 List[ScoredDocument]（LangChain Document 包装）。

支持延迟初始化模式，避免在模块导入时创建 Milvus 连接，
确保在事件循环运行后再执行异步操作。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter
from llama_index.vector_stores.milvus import MilvusVectorStore

from ..base import BaseRetriever, ScoredDocument
from .milvus_store import create_milvus_hybrid_store, create_milvus_hybrid_index

logger = logging.getLogger(__name__)


def _node_to_langchain_document(node_with_score: NodeWithScore) -> Document:
    """将 LlamaIndex NodeWithScore 转换为 LangChain Document。

    字段映射：
      - node.text       -> page_content
      - node.metadata   -> metadata（原样保留）
    
    Milvus 存储的元数据字段（type/domain/term/aliases 等）
    与 pgvector 路径完全一致，BusinessRagMiddleware 无感知。
    """
    node = node_with_score.node
    return Document(
        page_content=node.get_content() or "",
        metadata=node.metadata or {},
    )


class MilvusHybridRetriever(BaseRetriever):
    """LlamaIndex + Milvus 混合检索器（支持延迟初始化）。

    通过 LlamaIndex 的 hybrid 检索模式（dense + BM25 + RRF）召回候选文档，
    并将结果适配为 BaseRetriever 规范的 List[ScoredDocument] 输出。

    支持两种初始化模式：
    1. 立即初始化：传入已创建的 MilvusVectorStore（向后兼容）
    2. 延迟初始化：传入 store_params 字典，在首次调用 retrieve() 时创建连接

    Attributes:
        _store_params: MilvusVectorStore 初始化参数（延迟初始化用）。
        _store: 延迟初始化的 MilvusVectorStore 实例。
        _index: 延迟初始化的 VectorStoreIndex 实例。
        _similarity_top_k: 默认检索返回数量。
    """

    def __init__(
        self,
        store: Optional[MilvusVectorStore] = None,
        store_params: Optional[Dict[str, Any]] = None,
        similarity_top_k: int = 5,
    ) -> None:
        """初始化检索器（支持延迟初始化）。

        Args:
            store: 已初始化的 MilvusVectorStore（立即初始化模式，向后兼容）。
            store_params: MilvusVectorStore 初始化参数字典（延迟初始化模式）。
                         格式: {
                             "uri": str,
                             "collection_name": str,
                             "embed_dim": int,
                             "rrf_k": int,
                             "overwrite": bool,
                         }
            similarity_top_k: 检索默认返回数量（retrieve 方法的 k 参数优先级更高）。

        注意：
            - 如果同时提供 store 和 store_params，优先使用 store（立即初始化模式）。
            - 如果只提供 store_params，将在首次调用 retrieve() 时延迟初始化。
        """
        if store is not None:
            # 立即初始化模式（向后兼容）
            self._store = store
            self._index = create_milvus_hybrid_index(store)
            self._store_params = None
            logger.info(
                "MilvusHybridRetriever 初始化完成（立即模式）, default_top_k=%d",
                similarity_top_k
            )
        elif store_params is not None:
            # 延迟初始化模式
            self._store = None
            self._index = None
            self._store_params = store_params
            logger.info(
                "MilvusHybridRetriever 准备就绪（延迟初始化模式）, "
                "将在首次检索时初始化, default_top_k=%d",
                similarity_top_k
            )
        else:
            raise ValueError(
                "MilvusHybridRetriever 需要提供 store 或 store_params 参数"
            )
        
        self._similarity_top_k = similarity_top_k

    @property
    def _lazy_store(self) -> MilvusVectorStore:
        """延迟创建 MilvusVectorStore（首次访问时初始化）。

        Returns:
            已初始化的 MilvusVectorStore 实例。

        Raises:
            RuntimeError: 如果 store_params 未设置且 store 未初始化。
        """
        if self._store is None:
            if self._store_params is None:
                raise RuntimeError(
                    "MilvusHybridRetriever: store_params 未设置，无法延迟初始化"
                )
            
            logger.info(
                "MilvusHybridRetriever: 首次使用，正在初始化 Milvus Store... "
                "(uri=%s, collection=%s)",
                self._store_params.get("uri", "unknown"),
                self._store_params.get("collection_name", "unknown"),
            )
            
            self._store = create_milvus_hybrid_store(
                uri=self._store_params["uri"],
                collection_name=self._store_params["collection_name"],
                embed_dim=self._store_params["embed_dim"],
                rrf_k=self._store_params["rrf_k"],
                overwrite=self._store_params.get("overwrite", False),
            )
            
            logger.info("MilvusHybridRetriever: Milvus Store 初始化完成")
        
        return self._store

    @property
    def _lazy_index(self) -> VectorStoreIndex:
        """延迟创建 VectorStoreIndex（首次访问时初始化）。

        Returns:
            已初始化的 VectorStoreIndex 实例。
        """
        if self._index is None:
            logger.info("MilvusHybridRetriever: 正在创建 VectorStoreIndex...")
            self._index = create_milvus_hybrid_index(self._lazy_store)
            logger.info("MilvusHybridRetriever: VectorStoreIndex 创建完成")
        
        return self._index

    def retrieve(
        self,
        query: str,
        k: int = 5,
        score_threshold: Optional[float] = None,
        doc_type: str = "documentation",
        domain: Optional[str] = None,
    ) -> List[ScoredDocument]:
        """使用混合检索（向量 + BM25）查询文档。

        Args:
            query: 用户查询文本。
            k: 召回数量上限（覆盖初始化时的 similarity_top_k）。
            score_threshold: 相似度分数阈值，低于该值的结果被过滤；None 表示不过滤。
                             注意：混合检索的 RRF 分数范围与纯向量分数不同，
                             请根据实际调优后再启用此阈值。
            doc_type: 文档类型过滤（使用原生 MetadataFilters，在 Milvus 层面过滤）。
            domain: 业务域标识（使用原生 MetadataFilters，在 Milvus 层面过滤）。

        Returns:
            按 RRF 分数降序排列的 ScoredDocument 列表。
        """
        if not query or not query.strip():
            logger.warning("MilvusHybridRetriever: 查询为空，返回空结果")
            return []

        logger.info(
            "MilvusHybridRetriever: 开始混合检索, query='%s', k=%d, "
            "score_threshold=%s, doc_type=%s, domain=%s",
            query[:80],
            k,
            score_threshold,
            doc_type,
            domain,
        )

        try:
            # 构建元数据过滤器
            filters = []
            if doc_type:
                filters.append(
                    MetadataFilter(key="type", value=doc_type, operator="==")
                )
            if domain:
                filters.append(
                    MetadataFilter(key="domain", value=domain, operator="==")
                )
            
            metadata_filters = MetadataFilters(filters=filters) if filters else None
            
            # 延迟初始化：首次调用时才创建 index 和 retriever
            retriever_kwargs = {
                "vector_store_query_mode": "hybrid",
                "similarity_top_k": k,
            }
            if metadata_filters is not None:
                retriever_kwargs["filters"] = metadata_filters
                logger.info(
                    "MilvusHybridRetriever: 应用元数据过滤, filters=%s",
                    [{"key": f.key, "value": f.value, "operator": f.operator} for f in filters]
                )
            
            retriever = self._lazy_index.as_retriever(**retriever_kwargs)
            nodes_with_scores: List[NodeWithScore] = retriever.retrieve(query)

            # 转换为 ScoredDocument（LangChain Document 包装）
            results: List[ScoredDocument] = []
            for node_ws in nodes_with_scores:
                score = float(node_ws.score or 0.0)

                # 分数阈值过滤
                if score_threshold is not None and score < score_threshold:
                    logger.debug(
                        "MilvusHybridRetriever: 过滤低分文档 score=%.4f < threshold=%.4f",
                        score,
                        score_threshold,
                    )
                    continue

                lc_doc = _node_to_langchain_document(node_ws)
                results.append(ScoredDocument(document=lc_doc, score=score))

            # 按分数降序排序（LlamaIndex 通常已排序，此处保险起见）
            results.sort(key=lambda x: x.score, reverse=True)

            if results:
                scores = [r.score for r in results]
                logger.info(
                    "MilvusHybridRetriever: 检索完成, 命中=%d, score_range=[%.4f, %.4f]",
                    len(results),
                    min(scores),
                    max(scores),
                )
            else:
                logger.info("MilvusHybridRetriever: 检索完成, 未命中文档")

            return results

        except Exception as exc:
            # 增强错误处理，提供更详细的错误信息
            error_msg = str(exc).lower()
            if "event loop" in error_msg or "asyncio" in error_msg:
                logger.error(
                    "MilvusHybridRetriever: 事件循环错误，可能是延迟初始化时机问题: %s", exc
                )
            elif "connection" in error_msg or "connect" in error_msg:
                logger.error(
                    "MilvusHybridRetriever: Milvus 连接失败，请检查服务是否运行: %s", exc
                )
            else:
                logger.error(
                    "MilvusHybridRetriever: 检索过程中发生异常，将返回空结果: %s", exc
                )
            return []
