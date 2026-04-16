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
from .api import router
from .services import initialize_agent_service, shutdown_agent_service
from .agent.utils import ensure_windows_selector_loop

ensure_windows_selector_loop()


@asynccontextmanager  # 装饰器，将函数标记为异步上下文管理器
async def lifespan(app: FastAPI):
    # 应用启动时执行 - 创建数据库表
    logger.info("App 启动")
    create_tables()  # 创建数据库和数据表
    await initialize_agent_service()
    yield
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


# crud: create/read/update/delete
# api/endpoint/router
@app.get("/")
async def read_root():
    return {"Hellosq111ee1": "FastAPI"}
