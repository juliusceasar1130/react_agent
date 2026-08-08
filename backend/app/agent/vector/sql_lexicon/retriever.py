# backend/app/agent/vector/sql_lexicon/retriever.py
import asyncio
import logging
from typing import Dict, Any, List
from llama_index.core import VectorStoreIndex
from backend.app.config import settings
from backend.app.agent.vector.sql_lexicon.store import get_milvus_vector_store

logger = logging.getLogger(__name__)

class DatabaseLexiconRetriever:
    """在线 RAG：三路并发检索元数据与数据库词典（表结构 DDL、列值字典、行实体字典）。"""
    
    def __init__(self) -> None:
        logger.info("Initializing DatabaseLexiconRetriever and connecting to Milvus collections...")
        
        # 统一配置 LlamaIndex 全局 embedding
        from backend.app.agent.vector.embedding_provider import configure_llama_index_settings
        try:
            configure_llama_index_settings(settings)
        except Exception as e:
            logger.warning(f"Failed to configure global LlamaIndex settings: {e}")
        
        # 1. table_schema_store (表级结构检索)
        self.schema_store = get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name="table_schema_store",
            embed_dim=settings.milvus_embed_dim,
            rrf_k=getattr(settings, "milvus_rrf_k", 60)
        )
        self.schema_index = VectorStoreIndex.from_vector_store(self.schema_store)
        self.schema_retriever = self.schema_index.as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=getattr(settings, "lexicon_schema_top_k", 3)
        )
        
        # 2. db_value_lexicon (列去重值字典)
        self.value_store = get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name="db_value_lexicon",
            embed_dim=settings.milvus_embed_dim,
            rrf_k=getattr(settings, "milvus_rrf_k", 60)
        )
        self.value_index = VectorStoreIndex.from_vector_store(self.value_store)
        self.value_retriever = self.value_index.as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=getattr(settings, "lexicon_value_top_k", 5)
        )
        
        # 3. db_row_lexicon (行实体物理值对齐)
        self.row_store = get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name="db_row_lexicon",
            embed_dim=settings.milvus_embed_dim,
            rrf_k=getattr(settings, "milvus_rrf_k", 60)
        )
        self.row_index = VectorStoreIndex.from_vector_store(self.row_store)
        self.row_retriever = self.row_index.as_retriever(
            vector_store_query_mode="hybrid",
            similarity_top_k=getattr(settings, "lexicon_row_top_k", 5)
        )
        
        logger.info("DatabaseLexiconRetriever connected successfully.")

    async def retrieve_all(self, query: str) -> Dict[str, List[Any]]:
        """并行三路召回并隔离异常，确保对运行流程无阻塞阻断。"""
        if not query:
            return {"tables": [], "values": [], "rows": []}
            
        try:
            results = await asyncio.gather(
                self.schema_retriever.aretrieve(query),
                self.value_retriever.aretrieve(query),
                self.row_retriever.aretrieve(query),
                return_exceptions=True
            )
            tables = results[0] if not isinstance(results[0], Exception) else []
            values = results[1] if not isinstance(results[1], Exception) else []
            rows = results[2] if not isinstance(results[2], Exception) else []

            if isinstance(results[0], Exception):
                logger.warning(f"⚠️ [DatabaseLexiconRetriever] schema_retriever 检索异常: {results[0]}")
            if isinstance(results[1], Exception):
                logger.warning(f"⚠️ [DatabaseLexiconRetriever] value_retriever 检索异常: {results[1]}")
            if isinstance(results[2], Exception):
                logger.warning(f"⚠️ [DatabaseLexiconRetriever] row_retriever 检索异常: {results[2]}")

            return {
                "tables": tables,
                "values": values,
                "rows": rows
            }
        except Exception as e:
            logger.error(f"❌ [DatabaseLexiconRetriever] 三路数据库词典并发检索失败: {str(e)}", exc_info=True)
            return {"tables": [], "values": [], "rows": []}

    def retrieve_all_sync(self, query: str) -> Dict[str, List[Any]]:
        """同步三路召回并隔离异常。"""
        if not query:
            return {"tables": [], "values": [], "rows": []}
            
        def _safe_retrieve(retriever, name: str) -> List[Any]:
            try:
                return retriever.retrieve(query)
            except Exception as e:
                logger.warning(f"⚠️ [DatabaseLexiconRetriever] {name} 同步检索异常: {e}")
                return []

        return {
            "tables": _safe_retrieve(self.schema_retriever, "schema_retriever"),
            "values": _safe_retrieve(self.value_retriever, "value_retriever"),
            "rows": _safe_retrieve(self.row_retriever, "row_retriever")
        }
