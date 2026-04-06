"""
业务技能注册中心。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增领域技能与场景技能注册能力
- 保留旧版 `SKILLS` 导出，兼容现有中间件与测试代码
- 注册 `realtime_area_body_count` 实时区域车身数量场景
"""

from collections import defaultdict

from backend.app.skills.assets import read_asset_text
from backend.app.skills.domains.paint_shop_vehicle_tracking.meta import DOMAIN_META

# from backend.app.skills.domains.paint_shop_vehicle_tracking.scenarios.daily_area_body_count import (
#     SCENARIO as DAILY_AREA_BODY_COUNT,
# )
from backend.app.skills.domains.paint_shop_vehicle_tracking.scenarios.realtime_area_body_count import (
    SCENARIO as REALTIME_AREA_BODY_COUNT,
)
from backend.app.skills.models import DomainSkill, ScenarioSkill, Skill
from backend.app.skills.renderers import render_domain_for_llm


def _build_scenario_summaries(scenarios: list[ScenarioSkill]) -> list[str]:
    return [f"- **{item['name']}**: {item['description']}" for item in scenarios]


_RAW_SCENARIOS: dict[str, list[ScenarioSkill]] = defaultdict(list)
# _RAW_SCENARIOS[DAILY_AREA_BODY_COUNT["skill_name"]].append(DAILY_AREA_BODY_COUNT)
_RAW_SCENARIOS[REALTIME_AREA_BODY_COUNT["skill_name"]].append(REALTIME_AREA_BODY_COUNT)

SCENARIOS_BY_SKILL: dict[str, list[ScenarioSkill]] = dict(_RAW_SCENARIOS)

DOMAIN_SKILLS: dict[str, DomainSkill] = {
    DOMAIN_META["name"]: {
        "name": DOMAIN_META["name"],
        "description": DOMAIN_META["description"],
        "domain_content": read_asset_text("paint_shop_vehicle_tracking/domain.md"),
        "scenario_summaries": _build_scenario_summaries(
            SCENARIOS_BY_SKILL.get(DOMAIN_META["name"], [])
        ),
        "tags": DOMAIN_META["tags"],
    }
}

SKILLS: list[Skill] = [
    {
        "name": domain["name"],
        "description": domain["description"],
        "content": render_domain_for_llm(
            domain,
            SCENARIOS_BY_SKILL.get(domain["name"], []),
        ),
    }
    for domain in DOMAIN_SKILLS.values()
]


def get_skill_by_name(skill_name: str) -> DomainSkill | None:
    """按名称获取领域技能。"""
    return DOMAIN_SKILLS.get(skill_name)


def list_scenarios_by_skill(skill_name: str) -> list[ScenarioSkill]:
    """列出指定领域下的场景技能。"""
    return list(SCENARIOS_BY_SKILL.get(skill_name, []))


def get_scenario_by_name(skill_name: str, scenario_name: str) -> ScenarioSkill | None:
    """按领域和场景名称获取场景技能。"""
    for scenario in SCENARIOS_BY_SKILL.get(skill_name, []):
        if scenario["name"] == scenario_name:
            return scenario
    return None
