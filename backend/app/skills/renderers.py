"""
业务技能渲染器。

修改时间: 2026-04-05 Asia/Shanghai
主要修改内容:
- 新增领域技能与场景技能的 LLM 文本渲染能力
- 支持场景资产引用摘要和 SQL 模板展示
"""

from backend.app.skills.assets import read_asset_text
from backend.app.skills.models import DomainSkill, ScenarioSkill


def render_domain_for_llm(
    domain: DomainSkill,
    scenarios: list[ScenarioSkill],
) -> str:
    """将领域技能渲染为给 LLM 使用的加载文本。"""
    scenario_lines = domain["scenario_summaries"]
    if not scenario_lines:
        scenario_lines = ["- 暂无已注册场景"]

    return "\n".join(
        [
            f"# 领域技能：{domain['name']}",
            "",
            domain["domain_content"],
            "",
            "## 可用场景摘要",
            *scenario_lines,
            "",
            "## 使用规则",
            "- 先理解本领域的公共表结构、字段含义和业务规则。",
            "- 若用户问题属于固定统计或固定流程场景，优先加载对应场景技能。",
            "- 场景技能用于补充固定流程、关键口径和模板引用，不替代领域技能本身。",
        ]
    ).strip()


def _render_asset_refs(title: str, refs: list[dict]) -> list[str]:
    if not refs:
        return [f"## {title}", "- 暂无"]

    lines = [f"## {title}"]
    for ref in refs:
        lines.append(
            f"- {ref['name']} ({ref['type']}): {ref['description']} [path={ref['path']}]"
        )
    return lines


def render_scenario_for_llm(scenario: ScenarioSkill) -> str:
    """将场景技能渲染为给 LLM 使用的加载文本。"""
    lines = [
        f"# 场景技能：{scenario['title']} ({scenario['name']})",
        "",
        f"所属领域：{scenario['skill_name']}",
        f"场景描述：{scenario['description']}",
        "",
        "## 触发问法示例",
        *[f"- {item}" for item in scenario["triggers"]],
        "",
        "## 意图关键词",
        f"- {', '.join(scenario['intent_keywords'])}",
        "",
        "## 输入参数",
        f"- 必填: {', '.join(scenario['required_inputs']) or '无'}",
        f"- 可选: {', '.join(scenario['optional_inputs']) or '无'}",
        "",
        "## 固定流程",
        *[
            f"{index}. {step}"
            for index, step in enumerate(scenario["workflow"], start=1)
        ],
        "",
        "## 统计规则",
        *[f"- {item}" for item in scenario["rules"]],
        "",
        "## 易错点",
        *[f"- {item}" for item in scenario["gotchas"]],
        "",
        "## 输出契约",
        f"- {scenario['output_contract']}",
        "",
    ]

    lines.extend(_render_asset_refs("模板资产", scenario["sql_template_refs"]))
    lines.append("")
    lines.extend(_render_asset_refs("脚本资产", scenario["script_refs"]))

    if scenario["sql_template_refs"]:
        first_sql_ref = scenario["sql_template_refs"][0]
        sql_text = read_asset_text(first_sql_ref["path"])
        lines.extend(
            [
                "",
                f"## SQL 模板示例：{first_sql_ref['name']}",
                "```sql",
                sql_text,
                "```",
            ]
        )

    return "\n".join(lines).strip()
