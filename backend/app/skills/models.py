"""
业务技能数据模型。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增领域技能、场景技能与资产引用的数据结构
- 保留兼容旧版 `SKILLS` 的 `Skill` 结构
"""

from typing import TypedDict


class Skill(TypedDict):
    """兼容旧版中间件与测试脚本的领域技能摘要结构。"""

    name: str
    description: str
    content: str


class AssetRef(TypedDict):
    """外部资产引用。"""

    type: str
    name: str
    path: str
    description: str


class ScenarioSkill(TypedDict):
    """二级披露的固定场景技能定义。"""

    skill_name: str
    name: str
    title: str
    description: str
    triggers: list[str]
    intent_keywords: list[str]
    required_inputs: list[str]
    optional_inputs: list[str]
    workflow: list[str]
    rules: list[str]
    gotchas: list[str]
    output_contract: str
    sql_template_refs: list[AssetRef]
    script_refs: list[AssetRef]


class DomainSkill(TypedDict):
    """领域级技能定义。"""

    name: str
    description: str
    domain_content: str
    scenario_summaries: list[str]
    tags: list[str]
