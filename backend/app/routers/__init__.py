from fastapi import APIRouter
from backend.app.routers import chat, sessions, skills, admin, artifacts, _analytics, scenarios

router = APIRouter(prefix="/api/chat", tags=["chat"])
router.include_router(chat.router)
router.include_router(sessions.router)
router.include_router(skills.router)
router.include_router(admin.router)
router.include_router(artifacts.router)
router.include_router(_analytics.router)

scenarios_router = scenarios.router
init_analytics_engine = _analytics.init_analytics_engine

__all__ = ["router", "scenarios_router", "init_analytics_engine"]
