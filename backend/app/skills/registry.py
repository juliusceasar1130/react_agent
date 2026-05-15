"""
业务技能注册中心。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 新增领域技能与场景技能注册能力
- 保留旧版 `SKILLS` 导出，兼容现有中间件与测试代码
- 升级为基于目录约定的领域/场景自动发现
"""

from collections import defaultdict

from backend.app.skills.assets import read_text_file
from backend.app.skills.discovery import discover_domains, discover_scenarios
from backend.app.skills.models import DomainSkill, ScenarioSkill, Skill
from backend.app.skills.renderers import render_domain_for_llm


def _build_scenario_summaries(scenarios: list[ScenarioSkill]) -> list[str]:
    return [f"- **{item['name']}**: {item['description']}" for item in scenarios]


_DISCOVERED_DOMAINS = discover_domains()

_RAW_SCENARIOS: dict[str, list[ScenarioSkill]] = defaultdict(list)
for domain_name, domain in _DISCOVERED_DOMAINS.items():
    for scenario in discover_scenarios(domain):
        _RAW_SCENARIOS[domain_name].append(scenario)

SCENARIOS_BY_SKILL: dict[str, list[ScenarioSkill]] = {
    skill_name: sorted(items, key=lambda item: item["name"])
    for skill_name, items in _RAW_SCENARIOS.items()
}

DOMAIN_SKILLS: dict[str, DomainSkill] = {
    domain_name: {
        "name": domain_name,
        "title": domain.meta.get("title", domain_name),
        "description": domain.meta["description"],
        "domain_content": read_text_file(domain.domain_dir / "domain.md"),
        "scenario_summaries": _build_scenario_summaries(
            SCENARIOS_BY_SKILL.get(domain_name, [])
        ),
        "tags": list(domain.meta["tags"]),
        "domain_root": str(domain.domain_dir),
    }
    for domain_name, domain in _DISCOVERED_DOMAINS.items()
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
