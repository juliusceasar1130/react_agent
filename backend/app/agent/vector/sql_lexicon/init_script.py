# backend/app/agent/vector/sql_lexicon/init_script.py
import logging
from backend.app.agent.vector.embedding_provider import configure_llama_index_settings
from backend.app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """使用公共 MilvusStore 物理覆盖初始化空集合"""
    configure_llama_index_settings(settings)
    collections = ["table_schema_store", "db_value_lexicon", "db_row_lexicon"]
    
    from backend.app.agent.vector.sql_lexicon.store import get_milvus_vector_store
    for name in collections:
        logger.info(f"正在物理覆盖创建 Milvus 集合: {name} ...")
        get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name=name,
            embed_dim=settings.milvus_embed_dim,
            overwrite=True
        )
    logger.info("🎉 所有三层检索 Milvus 集合已物理初始化完成！")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
