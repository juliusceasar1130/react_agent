# backend/app/agent/state.py
"""
Agent 状态定义

定义 Agent 使用的自定义状态类型，用于追踪对话过程中的额外状态信息。
"""

from typing import List, Optional

from langchain.agents.middleware import AgentState
from langchain_core.documents import Document
from typing_extensions import NotRequired


class CustomState(AgentState):
    """
    扩展的 Agent 状态类型

    Attributes:
        skills_loaded: 已加载的技能名称列表，用于追踪当前对话中加载了哪些业务技能
        rag_context: 检索到的业务知识文档列表
        rag_query: 触发检索的用户查询
    """

    skills_loaded: NotRequired[List[str]]
    rag_context: NotRequired[List[Document]]
    rag_query: NotRequired[str]