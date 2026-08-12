"""
SQL 执行层 (Executor)

职责：加载场景 SQL 模板，安全过滤与绑定参数转换，执行查询返回原始行。
"""

import logging
from typing import Any
from sqlalchemy import text

logger = logging.getLogger(__name__)


def build_executed_sql(
    raw_sql: str,
    parameters_def: dict[str, Any],
    user_params: dict[str, Any],
    template_name: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    解析 SQL 模板：
    1. 判定为空的参数（None, "", 纯空白）整行删除
    2. 有值的参数使用 sql_fragment (优先读取 template_sql_fragments[template_name]) 替换，将 {value} 转化为命名参数 :param_name
    3. 系统默认全局将 LIKE 转换为 ILIKE，实现不区分大小写的模糊匹配
    """
    bind_vars = {}
    lines = raw_sql.splitlines()
    final_lines = []

    for line in lines:
        matched_placeholder = False
        for param_name, param_def in parameters_def.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in line:
                matched_placeholder = True
                val = user_params.get(param_name)
                # 判定非空值
                if val is not None and str(val).strip() != "":
                    # 优先获取模板专属的 SQL 片段，降级使用通用 sql_fragment
                    template_fragments = param_def.get("template_sql_fragments", {})
                    sql_fragment = (template_fragments.get(template_name) if template_name else None) or param_def.get("sql_fragment", "")
                    bind_placeholder = f":{param_name}"
                    
                    # 替换 {value}
                    replaced_fragment = sql_fragment.replace("{value}", bind_placeholder)
                    
                    # 系统默认全局行为：将 LIKE 自动转换为 PostgreSQL 的 ILIKE (不区分大小写模糊匹配)
                    if " LIKE " in replaced_fragment:
                        replaced_fragment = replaced_fragment.replace(" LIKE ", " ILIKE ")

                    # 仅当片段中实际包含占位符时进行物理类型转换与变量绑定
                    if bind_placeholder in replaced_fragment:
                        p_type = param_def.get("type", "string")
                        if p_type == "integer":
                            bind_vars[param_name] = int(val)
                        elif p_type == "float":
                            bind_vars[param_name] = float(val)
                        else:
                            bind_vars[param_name] = str(val)

                    line = line.replace(placeholder, replaced_fragment)
                    final_lines.append(line)
                else:
                    # 空值参数：剔除整行
                    pass
                break

        if not matched_placeholder:
            final_lines.append(line)

    clean_sql = "\n".join(final_lines)
    return clean_sql, bind_vars


def execute_scenario(
    domain_name: str,
    scenario_name: str,
    params: dict[str, Any],
    template_name: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple], list[str], int]:
    """
    加载模板并安全执行查询，返回 (rows, column_names, total_count)。
    """
    from backend.app.skills.registry import get_scenario_by_name
    from backend.app.skills.assets import read_asset_text
    scenario = get_scenario_by_name(domain_name, scenario_name)
    if not scenario:
        raise ValueError(f"Scenario not found: {domain_name}/{scenario_name}")

    target_template = template_name or scenario.get("default_template")
    sql_refs = scenario.get("sql_template_refs", [])
    
    ref_item = None
    if target_template:
        for ref in sql_refs:
            if ref["name"] == target_template:
                ref_item = ref
                break
    if not ref_item and sql_refs:
        ref_item = sql_refs[0]
        
    if not ref_item:
        raise ValueError(f"No SQL template ref found for scenario {domain_name}/{scenario_name}")

    # 读取模板文本
    raw_sql = read_asset_text(ref_item, scenario=scenario)
    parameters_def = scenario.get("parameters", {})

    # 构建并净化 SQL
    clean_sql, bind_vars = build_executed_sql(raw_sql, parameters_def, params, template_name=target_template)

    from backend.app.config import settings
    from sqlalchemy import create_engine
    engine = create_engine(settings.analytics_database_url)

    with engine.connect() as conn:
        # 清理 SQL 末尾分号后再进行 COUNT(*) 子查询包裹
        sql_base = clean_sql.strip().rstrip(";")
        count_sql = f"SELECT COUNT(*) FROM ({sql_base}) AS _total_count_subquery"
        total_count_res = conn.execute(text(count_sql), bind_vars)
        total_count = total_count_res.scalar() or 0

        # 分页参数计算与子查询包裹
        safe_page = max(1, page)
        safe_page_size = max(1, min(500, page_size))
        offset = (safe_page - 1) * safe_page_size

        page_sql = f"SELECT * FROM ({sql_base}) AS _page_subquery LIMIT {safe_page_size} OFFSET {offset}"

        # 执行分页 SQL
        result = conn.execute(text(page_sql), bind_vars)
        columns = list(result.keys())
        rows = [tuple(row) for row in result.fetchall()]
        return rows, columns, total_count
