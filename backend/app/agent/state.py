# backend/app/agent/state.py
"""
Agent 状态定义。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增 `scenarios_loaded`、`active_skill`、`active_scenario`
- 为二级技能披露与后续模板执行预留状态字段
"""

from typing import Annotated, Any, List

from langchain.agents.middleware import AgentState
from langchain_core.documents import Document
from typing_extensions import NotRequired


def _last_wins(_a: Any, b: Any) -> Any:
    """Reducer: 后写入的值覆盖前一个值。"""
    return b


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
        context_warning: 当前会话最近一次模型调用的上下文预警 payload
    """

    skills_loaded: NotRequired[Annotated[List[str], _last_wins]]
    scenarios_loaded: NotRequired[Annotated[List[str], _last_wins]]
    active_skill: NotRequired[Annotated[str | None, _last_wins]]
    active_scenario: NotRequired[Annotated[str | None, _last_wins]]
    rag_context: NotRequired[List[Document]]
    rag_query: NotRequired[str]
    context_warning: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    lexicon_context: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    tool_artifact: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
