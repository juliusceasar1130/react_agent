import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 配置日志（必须在导入其他模块之前）- 2026-01-02
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from .database import get_db, create_tables
from .routers import router, scenarios_router, init_analytics_engine
from .services import initialize_agent_service, shutdown_agent_service
from .agent.utils import ensure_windows_selector_loop

ensure_windows_selector_loop()


async def _periodic_artifact_gc_loop(interval_minutes: int = 60):
    """后台周期性工件垃圾回收循环。"""
    from backend.app.artifacts import get_artifact_store
    logger.info("ArtifactStore: 启动后台定时 GC 任务 (周期=%d分钟)", interval_minutes)
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            store = get_artifact_store()
            cleaned = await asyncio.to_thread(store.cleanup_expired)
            if cleaned > 0:
                logger.info("ArtifactStore: 定期 GC 完成，清理 %d 个超期工件", cleaned)
        except asyncio.CancelledError:
            logger.debug("ArtifactStore: 后台 GC 任务已取消")
            break
        except Exception as exc:
            logger.warning("ArtifactStore: 后台 GC 循环捕获异常: %s", exc)


@asynccontextmanager  # 装饰器，将函数标记为异步上下文管理器
async def lifespan(app: FastAPI):
    # 应用启动时执行 - 创建数据库表
    logger.info("App 启动")
    create_tables()  # 创建数据库和数据表
    init_analytics_engine()  # 预热 analytics 连接池
    await initialize_agent_service()

    # 启动工件定时清理 GC 任务
    gc_task = asyncio.create_task(_periodic_artifact_gc_loop(interval_minutes=60))

    # 异步非阻塞执行数据库物理词典 (DB Lexicon) 同步任务
    from .config import settings
    if settings.db_lexicon_sync_on_startup:
        logger.info("启动时异步执行数据库物理词典 (DB Lexicon) 同步")
        from backend.app.agent.vector.sql_lexicon.tasks import start_metadata_lexicon_sync_async
        start_metadata_lexicon_sync_async(overwrite=settings.milvus_overwrite)
    else:
        logger.info("配置已禁用启动时数据库物理词典 (DB Lexicon) 同步，跳过")
    
    yield
    gc_task.cancel()
    try:
        await gc_task
    except asyncio.CancelledError:
        pass
    await shutdown_agent_service()
    logger.info("App 关闭")


app = FastAPI(
    title="ChatGPT API",
    description="A simple API for ChatGPT",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加 CORS 中间件 - 2025-12-27
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(router)
app.include_router(scenarios_router)


# crud: create/read/update/delete
# api/endpoint/router
@app.get("/")
async def read_root():
    return {"Hellosq111ee1": "FastAPI"}
