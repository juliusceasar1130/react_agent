# backend/app/agent/tools/skill_tools.py
"""
技能加载工具。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 保留领域级 `load_skill`
- 新增场景级 `load_scenario`
- 引入 skills package 的注册中心与加载器
"""

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from backend.app.agent.utils import emit_stream_status
from backend.app.skills import (
    get_all_skills,
    get_scenario_by_name,
    get_skill_by_name,
    load_domain_content,
    load_scenario_content,
)


def _merge_names(existing: list[str], new_name: str) -> list[str]:
    merged = [*existing, new_name]
    return list(dict.fromkeys(merged))


def _build_load_skill_command(skill_name: str, runtime: ToolRuntime) -> Command:
    skill = get_skill_by_name(skill_name)
    if skill is None:
        available = ", ".join(s["name"] for s in get_all_skills())
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"Skill '{skill_name}' not found. "
                            f"Available skills: {available}"
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    # 1. 追加并保留已加载历史
    current_loaded = runtime.state.get("skills_loaded", [])
    new_loaded = list(current_loaded)
    if skill_name not in new_loaded:
        new_loaded.append(skill_name)

    # 2. 限制辅助技能堆积上限为 3 个，超出截断最先进入的 (FIFO)
    while len(new_loaded) > 3:
        new_loaded.pop(0)

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=(
                        f"已成功将当前主技能激活为 '{skill_name}'。\n"
                        f"历史加载过的技能 {new_loaded} 仍处于内存辅助参考状态，大模型可以直接跨表关联。"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "skills_loaded": new_loaded,
            "active_skill": skill_name,
        }
    )


def _build_load_scenario_command(
    skill_name: str,
    scenario_name: str,
    runtime: ToolRuntime,
) -> Command:
    if get_skill_by_name(skill_name) is None:
        available = ", ".join(s["name"] for s in get_all_skills())
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"Skill '{skill_name}' not found. "
                            f"Available skills: {available}"
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    loaded_skills = runtime.state.get("skills_loaded", [])
    if skill_name not in loaded_skills:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"Error: 请先使用 load_skill('{skill_name}') "
                            "加载领域技能后，再加载场景技能。"
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    scenario = get_scenario_by_name(skill_name, scenario_name)
    if scenario is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"Scenario '{scenario_name}' not found under "
                            f"skill '{skill_name}'."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    scenario_content = load_scenario_content(skill_name, scenario_name)
    scenario_key = f"{skill_name}.{scenario_name}"
    loaded_scenarios = _merge_names(
        runtime.state.get("scenarios_loaded", []),
        scenario_key,
    )

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=(
                        f"Loaded scenario: {skill_name}.{scenario_name}\n\n"
                        f"{scenario_content}"
                    ),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "scenarios_loaded": loaded_scenarios,
            "active_skill": skill_name,
            "active_scenario": scenario_name,
        }
    )


@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> Command:
    """
    Load the full content of a domain skill into the agent's context.

    Use this when you need detailed information about a business domain.
    The loaded content includes public schema knowledge, business rules, and
    a summary of fixed scenarios available under the domain.

    Args:
        skill_name: The name of the domain skill to load.
    """
    emit_stream_status(
        f"正在加载业务技能：{skill_name}",
        stage="retrieving",
        source="load_skill",
    )
    return _build_load_skill_command(skill_name, runtime)


@tool
def load_scenario(skill_name: str, scenario_name: str, runtime: ToolRuntime) -> Command:
    """
    Load the detailed playbook of a fixed scenario under a business domain.

    IMPORTANT: You must load the parent domain skill with load_skill() first.
    Use this when the user asks for a fixed reporting or statistics workflow
    and the domain skill content indicates there is a matching scenario.

    Args:
        skill_name: The parent domain skill name.
        scenario_name: The scenario name under the domain.
    """
    emit_stream_status(
        f"正在加载业务场景：{skill_name}.{scenario_name}",
        stage="retrieving",
        source="load_scenario",
    )
    return _build_load_scenario_command(skill_name, scenario_name, runtime)
