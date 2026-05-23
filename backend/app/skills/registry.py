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


import logging

logger = logging.getLogger(__name__)

class _RegistryState:
    def __init__(self):
        self.discovered_domains = {}
        self.scenarios_by_skill = {}
        self.domain_skills = {}
        self.skills = []

_state = _RegistryState()


def reload_skills() -> bool:
    """重新扫描并加载全部技能，使用 try-catch 隔离错误"""
    try:
        new_discovered = discover_domains()
        
        new_scenarios_raw = defaultdict(list)
        for domain_name, domain in new_discovered.items():
            for scenario in discover_scenarios(domain):
                new_scenarios_raw[domain_name].append(scenario)
                
        new_scenarios_by_skill = {
            k: sorted(v, key=lambda i: i["name"]) 
            for k, v in new_scenarios_raw.items()
        }
        
        new_domain_skills = {
            d_name: {
                "name": d_name,
                "title": domain.meta.get("title", d_name),
                "description": domain.meta["description"],
                "domain_content": read_text_file(domain.domain_dir / "domain.md"),
                "scenario_summaries": _build_scenario_summaries(
                    new_scenarios_by_skill.get(d_name, [])
                ),
                "tags": list(domain.meta["tags"]),
                "domain_root": str(domain.domain_dir),
            }
            for d_name, domain in new_discovered.items()
        }
        
        new_skills = [
            {
                "name": domain["name"],
                "description": domain["description"],
                "content": render_domain_for_llm(
                    domain,
                    new_scenarios_by_skill.get(domain["name"], []),
                ),
            }
            for domain in new_domain_skills.values()
        ]
        
        # 原子更新全局状态
        _state.discovered_domains = new_discovered
        _state.scenarios_by_skill = new_scenarios_by_skill
        _state.domain_skills = new_domain_skills
        _state.skills = new_skills
        logger.info("Skills reloaded successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to reload skills: {e}", exc_info=True)
        return False

# 初始加载
reload_skills()

def get_all_skills() -> list[Skill]:
    """获取所有已注册的技能列表（用于注入提示词）"""
    return _state.skills

def get_domain_skills() -> dict[str, DomainSkill]:
    """获取领域技能全集字典"""
    return _state.domain_skills

def get_skill_by_name(skill_name: str) -> DomainSkill | None:
    """按名称获取领域技能。"""
    return _state.domain_skills.get(skill_name)


def list_scenarios_by_skill(skill_name: str) -> list[ScenarioSkill]:
    """列出指定领域下的场景技能。"""
    return list(_state.scenarios_by_skill.get(skill_name, []))


def get_scenario_by_name(skill_name: str, scenario_name: str) -> ScenarioSkill | None:
    """按领域和场景名称获取场景技能。"""
    for scenario in _state.scenarios_by_skill.get(skill_name, []):
        if scenario["name"] == scenario_name:
            return scenario
    return None

