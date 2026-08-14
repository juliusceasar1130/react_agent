# backend/app/agent/subagents/sql/prompts.py
import logging
import threading
from pathlib import Path
from langchain_core.prompts import PromptTemplate

from backend.app.agent.utils import MaterializedViewSQLDatabase
from backend.app.config import settings

logger = logging.getLogger(__name__)


class SystemPromptLoader:
    """系统提示词动态加载器，支持缓存和热重载。"""

    _lock = threading.Lock()

    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        self._cached_prompt: str = ""
        self._last_modified_time: float = 0.0

    def load(self, force_reload: bool = False) -> str:
        """加载提示词模板并返回（带缓存和热重载）。"""
        if not self.template_path.exists():
            raise FileNotFoundError(f"系统提示词模板文件不存在: {self.template_path}")

        mtime = self.template_path.stat().st_mtime
        should_reload = (
            not self._cached_prompt
            or force_reload
            or (settings.debug and mtime > self._last_modified_time)
        )

        if should_reload:
            with self._lock:
                if (
                    not self._cached_prompt
                    or force_reload
                    or (settings.debug and mtime > self._last_modified_time)
                ):
                    logger.info("加载系统提示词模板: %s", self.template_path)
                    self._cached_prompt = self.template_path.read_text(encoding="utf-8")
                    self._last_modified_time = mtime

        return self._cached_prompt


_system_prompt_loader = SystemPromptLoader(settings.system_prompt_path)


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    template_str = _system_prompt_loader.load()
    template = PromptTemplate.from_template(template_str)
    return template.format(
        dialect=db.dialect,
        top_k=settings.sql_agent_top_k,
    )
