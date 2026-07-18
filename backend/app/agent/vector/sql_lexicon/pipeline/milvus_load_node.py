# backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py
import logging
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import TextNode
from backend.app.agent.vector.sql_lexicon.pipeline.base import PipelineNode
from backend.app.agent.vector.sql_lexicon.store import get_milvus_vector_store

logger = logging.getLogger(__name__)


class MilvusIngestionNode(PipelineNode):
    """加载节点：将提取生成的 Documents 存入 Milvus 集合。

    使用 TextNode + VectorStoreIndex(nodes=...) 直接嵌入，跳过 SentenceSplitter
    分块，保证每个 Document 作为完整语义单元存入（1 文档 = 1 节点）。
    """

    def __init__(self, overwrite: bool = True):
        self.overwrite = overwrite

    def _index_nodes(self, settings, collection_name: str, docs: list) -> None:
        """将 Document 转为 TextNode（不分块）后嵌入到指定 Milvus 集合。"""
        if not docs:
            return
        store = get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name=collection_name,
            embed_dim=settings.milvus_embed_dim,
            overwrite=self.overwrite,
            rrf_k=settings.milvus_rrf_k,
        )
        ctx = StorageContext.from_defaults(vector_store=store)
        nodes = [TextNode(text=d.text, metadata=d.metadata) for d in docs]
        VectorStoreIndex(nodes=nodes, storage_context=ctx)
        logger.info(f"✨ [Pipeline] {collection_name} 载入成功（{len(nodes)} 个节点，无分块）。")

    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在写入向量至 Milvus 集合...")
        settings = context["settings"]

        self._index_nodes(settings, "table_schema_store", context.get("schema_docs", []))
        self._index_nodes(settings, "db_value_lexicon", context.get("val_docs", []))
        self._index_nodes(settings, "db_row_lexicon", context.get("row_docs", []))

        return context
