"""
业务技能注册中心导出。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 将单文件 `skills.py` 升级为 `skills/` package
- 保留 `SKILLS` 兼容导出，同时新增领域/场景查询接口
"""

from .loaders import load_domain_content, load_scenario_content
from .models import AssetRef, DomainSkill, ScenarioSkill, Skill
from .registry import (
    DOMAIN_SKILLS,
    SCENARIOS_BY_SKILL,
    SKILLS,
    get_scenario_by_name,
    get_skill_by_name,
    list_scenarios_by_skill,
)

__all__ = [
    "AssetRef",
    "DomainSkill",
    "ScenarioSkill",
    "Skill",
    "DOMAIN_SKILLS",
    "SCENARIOS_BY_SKILL",
    "SKILLS",
    "get_skill_by_name",
    "list_scenarios_by_skill",
    "get_scenario_by_name",
    "load_domain_content",
    "load_scenario_content",
]
