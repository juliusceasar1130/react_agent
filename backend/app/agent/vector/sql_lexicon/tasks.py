# backend/app/agent/vector/sql_lexicon/tasks.py
import logging
import threading

from backend.app.config import settings

logger = logging.getLogger(__name__)


def run_metadata_lexicon_sync(overwrite: bool = True):
    """
    通过 IngestionPipeline 执行全量同步表 DDL、列值白名单字典、行级白名单实体到 Milvus。
    """
    logger.info("🔄 [Sync Task] 正在通过 Pipeline 执行三层检索向量同步...")
    
    def _main_sync():
        try:
            from backend.app.agent.vector.sql_lexicon.pipeline.base import IngestionPipeline
            from backend.app.agent.vector.sql_lexicon.pipeline.extractor_nodes import (
                MetadataExtractorNode,
                TableDDLExtractorNode,
                ColumnLexiconExtractorNode,
                RowLexiconExtractorNode
            )
            from backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node import MilvusIngestionNode
            from backend.app.agent.utils.sql_database import build_postgres_search_path_engine_args
            from backend.app.agent.vector.embedding_provider import configure_llama_index_settings

            # 1. 配置环境
            configure_llama_index_settings(settings)
            engine_args = build_postgres_search_path_engine_args(settings.analytics_db_search_path)
            
            # 2. 组装 Pipeline 节点
            pipeline = IngestionPipeline([
                MetadataExtractorNode(),
                TableDDLExtractorNode(),
                ColumnLexiconExtractorNode(),
                RowLexiconExtractorNode(),
                MilvusIngestionNode(overwrite=overwrite)
            ])
            
            initial_context = {
                "settings": settings,
                "db_uri": settings.analytics_database_url,
                "engine_args": engine_args
            }
            
            # 3. 运行 Ingestion Pipeline
            pipeline.run(initial_context)
            logger.info("✨ [Sync Task] Pipeline 向量同步执行完毕。")
        except Exception as sync_err:
            logger.error(f"❌ [Sync Task] Pipeline 向量同步核心逻辑执行失败: {str(sync_err)}", exc_info=True)
            raise sync_err

    # 💡 核心修正：如果当前子线程没有活跃的 running event loop，使用 asyncio.run() 启动一个临时 running loop，
    # 否则（如在 pytest 异步测试或 FastAPI 主事件循环中）直接同步执行逻辑，让 PyMilvus 能正常检测到事件循环。
    import asyncio
    
    async def _async_wrapper():
        _main_sync()

    try:
        loop = asyncio.get_running_loop()
        # 已经在活跃的 asyncio 上下文中，直接执行同步流程
        _main_sync()
    except RuntimeError:
        # 子线程无活跃事件循环，使用 asyncio.run 创建 running loop
        try:
            asyncio.run(_async_wrapper())
        except Exception as e:
            logger.error(f"❌ [Sync Task] Pipeline 向量同步异步包裹执行失败: {str(e)}")


def start_metadata_lexicon_sync_async(overwrite: bool = True):
    """
    异步非阻塞后台线程启动同步
    """
    thread = threading.Thread(target=run_metadata_lexicon_sync, args=(overwrite,))
    thread.daemon = True
    thread.start()
