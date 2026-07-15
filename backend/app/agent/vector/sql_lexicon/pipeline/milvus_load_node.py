# backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py
import logging
from llama_index.core import VectorStoreIndex, StorageContext
from backend.app.agent.vector.sql_lexicon.pipeline.base import PipelineNode
from backend.app.agent.vector.sql_lexicon.store import get_milvus_vector_store

logger = logging.getLogger(__name__)

class MilvusIngestionNode(PipelineNode):
    """加载节点：将提取生成的 Documents 存入 Milvus 集合。"""
    
    def __init__(self, overwrite: bool = True):
        self.overwrite = overwrite
        
    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在写入向量至 Milvus 集合...")
        settings = context["settings"]
        overwrite = self.overwrite
        
        schema_docs = context.get("schema_docs", [])
        val_docs = context.get("val_docs", [])
        row_docs = context.get("row_docs", [])
        
        # 1. table_schema_store
        if schema_docs:
            store = get_milvus_vector_store(
                uri=settings.milvus_uri,
                collection_name="table_schema_store",
                embed_dim=settings.milvus_embed_dim,
                overwrite=overwrite,
                rrf_k=settings.milvus_rrf_k
            )
            ctx = StorageContext.from_defaults(vector_store=store)
            VectorStoreIndex.from_documents(schema_docs, storage_context=ctx)
            logger.info("✨ [Pipeline] table_schema_store 载入成功。")
            
        # 2. db_value_lexicon
        if val_docs:
            store = get_milvus_vector_store(
                uri=settings.milvus_uri,
                collection_name="db_value_lexicon",
                embed_dim=settings.milvus_embed_dim,
                overwrite=overwrite,
                rrf_k=settings.milvus_rrf_k
            )
            ctx = StorageContext.from_defaults(vector_store=store)
            VectorStoreIndex.from_documents(val_docs, storage_context=ctx)
            logger.info("✨ [Pipeline] db_value_lexicon 载入成功。")

        # 3. db_row_lexicon
        if row_docs:
            store = get_milvus_vector_store(
                uri=settings.milvus_uri,
                collection_name="db_row_lexicon",
                embed_dim=settings.milvus_embed_dim,
                overwrite=overwrite,
                rrf_k=settings.milvus_rrf_k
            )
            ctx = StorageContext.from_defaults(vector_store=store)
            VectorStoreIndex.from_documents(row_docs, storage_context=ctx)
            logger.info("✨ [Pipeline] db_row_lexicon 载入成功。")
            
        return context
