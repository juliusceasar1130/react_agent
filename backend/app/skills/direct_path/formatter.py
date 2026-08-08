"""
结果格式化层 (Formatter)

职责：将原始数据库查询行转化为前端渲染组件（Table / Scalar / Chart）直接可用的 JSON 数据形态。
"""

import math
from typing import Any


def format_result(
    rows: list[tuple],
    columns: list[str],
    output_type: str = "table",
    total_count: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """根据 output_type 将数据库查询行格式化为输出数据。"""
    actual_total = total_count if total_count is not None else len(rows)
    safe_page_size = max(1, page_size)
    total_pages = math.ceil(actual_total / safe_page_size) if actual_total > 0 else 1

    if output_type == "scalar":
        val = rows[0][0] if rows and len(rows[0]) > 0 else 0
        return {
            "type": "scalar",
            "value": val,
            "label": "查询结果",
        }
    
    if output_type == "chart":
        formatted_rows = [list(row) for row in rows]
        categories = [str(row[0]) for row in rows] if rows else []
        
        y_cols = columns[1:] if len(columns) > 1 else (columns if columns else ["数值"])
        series_data = []
        for idx, col_name in enumerate(y_cols, start=1 if len(columns) > 1 else 0):
            series_data.append({
                "name": col_name,
                "data": [row[idx] if idx < len(row) else None for row in rows] if rows else [],
            })
            
        return {
            "type": "chart",
            "columns": columns,
            "categories": categories,
            "series": series_data,
            "rows": formatted_rows,
            "row_count": len(formatted_rows),
            "total_count": actual_total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "is_truncated": False,
        }
    
    # 默认 "table"
    formatted_rows = [list(row) for row in rows]
    return {
        "type": "table",
        "columns": columns,
        "rows": formatted_rows,
        "row_count": len(formatted_rows),
        "total_count": actual_total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "is_truncated": False,
    }
