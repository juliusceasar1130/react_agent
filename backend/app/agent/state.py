# backend/app/agent/state.py
"""
Agent 状态定义。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增 `scenarios_loaded`、`active_skill`、`active_scenario`
- 为二级技能披露与后续模板执行预留状态字段
"""

from typing import List

from langchain.agents.middleware import AgentState
from langchain_core.documents import Document
from typing_extensions import NotRequired


class CustomState(AgentState):
    """
    扩展的 Agent 状态类型。

    Attributes:
        skills_loaded: 已加载的领域技能名称列表
        scenarios_loaded: 已加载的场景技能列表，采用 `skill.scenario` 复合键
        active_skill: 当前活跃领域技能
        active_scenario: 当前活跃场景技能
        rag_context: 检索到的业务知识文档列表
        rag_query: 触发检索的用户查询
    """

    skills_loaded: NotRequired[List[str]]
    scenarios_loaded: NotRequired[List[str]]
    active_skill: NotRequired[str]
    active_scenario: NotRequired[str]
    rag_context: NotRequired[List[Document]]
    rag_query: NotRequired[str]
