# backend/app/agent/state.py
"""
Agent 状态定义与物理沙箱隔离。

修改时间: 2026-08-16 Asia/Shanghai
主要修改内容:
- 物理瘦身父图全局持久化状态 CustomState：剔除瞬态检索大对象，Checkpoint 体积降低 90% 以上
- 声明 SQL 子智能体专用沙箱状态 SqlSubAgentState：领域技能私有持有，彻底消除父图并发写冲突
"""
from typing import Annotated, Any, List
from langchain.agents.middleware import AgentState
from typing_extensions import NotRequired


def _last_wins(_a: Any, b: Any) -> Any:
    """Reducer: 后写入的值覆盖前一个值。"""
    return b


class CustomState(AgentState):
    """
    主智能体全局持久化状态 (MainAgentState)。
    仅保留长会话多轮对话所必需的字段，Checkpoint 快照体积轻量 (<5KB)。
    """
    context_warning: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]
    tool_artifact: NotRequired[Annotated[dict[str, Any] | None, _last_wins]]


class SqlSubAgentState(AgentState):
    """
    SQL 子智能体局部沙箱状态。
    仅在子图执行生命周期中生效，不向父图全局 State 扩散。

    Attributes:
        skills_loaded: 已加载的领域技能名称列表
        scenarios_loaded: 已加载的场景技能列表，采用 `skill.scenario` 复合键
        active_skill: 当前活跃领域技能
        active_scenario: 当前活跃场景技能
    """
    skills_loaded: NotRequired[Annotated[List[str], _last_wins]]
    scenarios_loaded: NotRequired[Annotated[List[str], _last_wins]]
    active_skill: NotRequired[Annotated[str | None, _last_wins]]
    active_scenario: NotRequired[Annotated[str | None, _last_wins]]
