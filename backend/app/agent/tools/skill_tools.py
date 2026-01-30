# backend/app/agent/tools/skill_tools.py
"""
技能加载工具

提供 load_skill 工具，用于在对话过程中动态加载业务技能详情。
"""

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from backend.app.skills import SKILLS


@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> Command:
    """
    Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., 'sales_analytics')

    Returns:
        Command: Updates the agent state with skill content and tracks loaded skills
    """
    # 查找请求的技能
    for skill in SKILLS:
        if skill["name"] == skill_name:
            skill_content = f"Loaded skill: {skill_name}\n\n{skill['content']}"

            # 更新状态以追踪已加载的技能
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=skill_content,
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                    "skills_loaded": [skill_name],
                }
            )

    # 技能未找到，返回可用技能列表
    available = ", ".join(s["name"] for s in SKILLS)
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Skill '{skill_name}' not found. Available skills: {available}",
                    tool_call_id=runtime.tool_call_id,
                )
            ]
        }
    )
