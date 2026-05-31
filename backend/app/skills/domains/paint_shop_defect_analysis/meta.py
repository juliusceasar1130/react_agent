"""
涂装车间质量缺陷分析领域元数据。

修改时间: 2026-04-12 Asia/Shanghai
主要修改内容:
- 新增质量缺陷分析领域元数据，供技能注册中心自动发现
"""

DOMAIN_META = {
    "name": "paint_shop_defect_analysis",
    "title": "质量缺陷分析",
    "description": "涂装车间质量缺陷汇总分析领域，面向车型缺陷趋势、部位分布、tunnel/cycle 对比和黑车顶对比等问题。\n\n【触发关键词】缺陷、缺陷率、缺陷汇总、部位分布、tunnel、cycle、黑车顶、车型趋势、对比\n【强制调用规则】用户问题包含以上任一关键词时，Agent 必须先调用 load_skill(\"paint_shop_defect_analysis\") 加载领域知识，再组织 SQL。",
    "tags": ["paint_shop", "quality", "defect", "scenario_enabled"],
}
