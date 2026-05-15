"""
业务技能数据模型。

修改时间: 2026-04-06 Asia/Shanghai
主要修改内容:
- 新增领域技能、场景技能与资产引用的数据结构
- 保留兼容旧版 `SKILLS` 的 `Skill` 结构
- 新增 ParameterDefinition 参数定义类型
- 增加场景资产 `scope` 语义与自动发现所需的内部路径字段
"""

from typing import NotRequired, TypedDict


class Skill(TypedDict):
    """兼容旧版中间件与测试脚本的领域技能摘要结构。"""

    name: str
    description: str
    content: str


class AssetRef(TypedDict):
    """外部资产引用。"""

    type: str
    name: str
    scope: str
    path: str
    description: str


class ParameterDefinition(TypedDict):
    """场景参数定义，用于指导 LLM 动态填充参数。"""

    type: str  # "array", "string", "integer" 等
    items_type: str  # 仅当 type="array" 时使用，表示数组元素类型
    description: str  # 参数用途说明
    required: bool  # 是否必填
    source_column: str  # 数据库列名
    source_table: str  # 可选值来源表（用于 LLM 查询可选值）
    example_values: list[str]  # 示例值
    usage: str  # 使用方式说明
    sql_fragment: str  # SQL 片段模板，{values} 为占位符


class ScenarioSkill(TypedDict):
    """二级披露的固定场景技能定义。"""

    skill_name: str
    name: str
    title: str
    description: str
    example_questions: list[str]  # 新增：首页展示的示例问题
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
    parameters: NotRequired[dict[str, ParameterDefinition]]
    scenario_root: NotRequired[str]
    domain_root: NotRequired[str]


class DomainSkill(TypedDict):
    """领域级技能定义。"""

    name: str
    title: str  # 新增：首页展示的中文标题
    description: str
    domain_content: str
    scenario_summaries: list[str]
    tags: list[str]
    domain_root: NotRequired[str]
