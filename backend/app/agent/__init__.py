# backend/app/agent/__init__.py
"""
SQL Agent 模块

提供模块化的 SQL Agent 服务，包含：
- 状态定义
- 中间件
- 工具
- 服务
"""

from backend.app.agent.state import CustomState
from backend.app.agent.service import SQLAgentService, agent_service
from backend.app.agent.middleware import SkillMiddleware
from backend.app.agent.tools import load_skill, create_wrapped_query_tool
from backend.app.agent.utils import (
    normalize_dates_in_text,
    fetch_table_definitions_with_comments,
)

__all__ = [
    # 服务
    "SQLAgentService",
    "agent_service",
    # 状态
    "CustomState",
    # 中间件
    "SkillMiddleware",
    # 工具
    "load_skill",
    "create_wrapped_query_tool",
    # 工具函数
    "normalize_dates_in_text",
    "fetch_table_definitions_with_comments",
]

