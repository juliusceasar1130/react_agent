# backend/app/agent/subagents/sql/prompts.py
import logging

from langchain_core.prompts import PromptTemplate

from backend.app.agent.utils import MaterializedViewSQLDatabase, SystemPromptLoader
from backend.app.config import settings

logger = logging.getLogger(__name__)

_system_prompt_loader = SystemPromptLoader(settings.system_prompt_path)


def _build_system_prompt(db: MaterializedViewSQLDatabase) -> str:
    """构建 Agent 系统提示词。"""
    template_str = _system_prompt_loader.load()
    template = PromptTemplate.from_template(template_str)
    return template.format(
        dialect=db.dialect,
        top_k=settings.sql_agent_top_k,
    )
