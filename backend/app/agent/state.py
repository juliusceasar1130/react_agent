# backend/app/agent/state.py
"""
Agent 状态定义。

修改时间: 2026-08-15 Asia/Shanghai
主要修改内容:
- 为 `rag_context` 和 `rag_query` 补充 `_last_wins` Reducer 声明
- 彻底解决多子智能体（CompiledSubAgent / task 工具）并发执行返回时触发的 LangGraph INVALID_CONCURRENT_GRAPH_UPDATE 并发状态写冲突
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
    rag_context: NotRequired[Annotated[List[Document], _last_wins]]
    rag_query: NotRequired[Annotated[str, _last_wins]]
    context_warning: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    lexicon_context: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    tool_artifact: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
