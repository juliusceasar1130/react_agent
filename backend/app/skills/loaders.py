"""
业务技能加载器。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增领域技能与场景技能的文本加载接口
- 统一封装二级披露的渲染逻辑
"""

from backend.app.skills.registry import (
    get_scenario_by_name,
    get_skill_by_name,
    list_scenarios_by_skill,
)
from backend.app.skills.renderers import render_domain_for_llm, render_scenario_for_llm


def load_domain_content(skill_name: str) -> str | None:
    """加载领域技能全文。"""
    domain = get_skill_by_name(skill_name)
    if domain is None:
        return None
    scenarios = list_scenarios_by_skill(skill_name)
    return render_domain_for_llm(domain, scenarios)


def load_scenario_content(skill_name: str, scenario_name: str) -> str | None:
    """加载场景技能全文。"""
    scenario = get_scenario_by_name(skill_name, scenario_name)
    if scenario is None:
        return None
    return render_scenario_for_llm(scenario)
