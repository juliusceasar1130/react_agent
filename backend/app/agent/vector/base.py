"""基础检索与精排抽象接口。

该模块定义了 RAG 管道中的核心抽象：
- BaseRetriever: 负责向量/文档检索
- BaseReranker: 负责候选文档的精排

注意：接口保持轻量，只表达核心语义，不与具体后端（pgvector、chroma 等）
或具体模型厂商（NVIDIA、OpenAI 等）耦合。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from langchain_core.documents import Document


@dataclass
class ScoredDocument:
    """带分数的文档包装类型。

    Attributes:
        document: 原始 LangChain Document 对象
        score: 文档相似度/相关性分数（越大越相关）
    """

    document: Document
    score: float


class BaseRetriever(ABC):
    """通用检索接口。

    所有具体检索实现（pgvector、chroma、hybrid 等）都应实现该抽象，
    以便在中间件与服务层进行解耦。
    """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        k: int = 5,
        score_threshold: Optional[float] = None,
        doc_type: str = "documentation",
        domain: Optional[str] = None,
    ) -> List[ScoredDocument]:
        """根据自然语言查询检索文档。

        Args:
            query: 用户查询文本。
            k: 召回数量上限。
            score_threshold: 相似度分数阈值，低于该值的结果将被过滤；None 表示不做阈值过滤。
            doc_type: 文档类型过滤，例如 "documentation" / "ddl" / "sql_example"。
            domain: 业务域标识，用于未来多业务线场景的隔离。

        Returns:
            按分数降序排列的 ScoredDocument 列表。
        """


class BaseReranker(ABC):
    """通用精排接口。

    精排层通常基于 cross-encoder 或 Rerank 模型，对候选文档重新排序。
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
    ) -> List[ScoredDocument]:
        """对候选文档进行重排序。

        Args:
            query: 用户查询文本。
            documents: 候选文档列表。

        Returns:
            按相关性分数降序排列的 ScoredDocument 列表。
        """

