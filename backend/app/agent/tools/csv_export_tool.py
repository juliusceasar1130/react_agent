# backend/app/agent/tools/csv_export_tool.py
"""
CSV 导出工具

当 SQL 查询结果超过系统硬限制（被截断）时，Agent 可调用此工具
将完整查询结果导出为 CSV 文件供用户下载，全程不经过 LLM 上下文。

修改时间: 2026-04-12 02:05 Asia/Shanghai
主要修改内容:
- 导出结果改为返回结构化文件元数据
- 配合后端下载接口支持前端安全下载
- 支持通过 engine_args 继承 analytics_db 的 search_path 配置
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any

from langchain.tools import ToolRuntime, tool as langchain_tool
from sqlalchemy import create_engine, text

from backend.app.agent.tools.sql_tools import FORBIDDEN_SQL_PATTERN
from backend.app.agent.utils import emit_stream_status
from backend.app.export_files import create_export_record, get_export_dir

logger = logging.getLogger(__name__)


def create_csv_export_tool(
    db_uri: str,
    engine_args: dict[str, Any] | None = None,
) -> Any:
    """
    创建 CSV 导出工具。

    Args:
        db_uri: 数据库连接 URI
        engine_args: 可选 SQLAlchemy 引擎参数，例如 PostgreSQL search_path

    Returns:
        export_to_csv 工具实例
    """

    @langchain_tool
    def export_to_csv(query: str, required_skill: str, runtime: ToolRuntime) -> str:
        """
        Execute a SQL query and export the full results to a CSV file for user download.

        Use this tool ONLY when the sql_db_query tool reports that results were truncated
        due to the system hard limit, and the user needs the complete dataset.
        This tool saves results directly to a CSV file without loading them into the LLM context.

        IMPORTANT: You must specify the 'required_skill' parameter with the exact skill name
        that this query depends on. The skill must have been loaded via load_skill() first.

        Args:
            query: A valid SQL SELECT query string.
            required_skill: The name of the skill/domain this query belongs to.
        """
        if FORBIDDEN_SQL_PATTERN.search(query):
            logger.warning(f"CSV 导出安全拦截：检测到危险 SQL 关键字。Query: {query}")
            return (
                "Error: 严重安全警告 - 该操作已被系统拦截。\n"
                "export_to_csv 仅允许执行只读查询 (SELECT)，禁止执行任何修改操作。"
            )

        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再导出数据。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。"
            )

        engine = None
        try:
            emit_stream_status(
                "正在导出完整 CSV 文件",
                stage="querying",
                source="export_to_csv",
            )

            export_dir = get_export_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"
            filepath = export_dir / filename

            engine = create_engine(db_uri, **(engine_args or {}))
            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns = list(result.keys())
                rows = result.fetchall()

            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow(row)

            row_count = len(rows)
            col_count = len(columns)
            file_size_kb = os.path.getsize(filepath) / 1024

            record = create_export_record(
                file_path=filepath,
                filename=filename,
                media_type="text/csv",
                row_count=row_count,
                col_count=col_count,
                columns=columns,
            )

            logger.info(
                "CSV 导出成功: %s (%d 行, %d 列, %.1f KB), file_id=%s",
                filepath, row_count, col_count, file_size_kb, record["file_id"],
            )
            emit_stream_status(
                "CSV 导出完成",
                stage="writing",
                source="export_to_csv",
            )

            record["message"] = "CSV 导出成功，前端可使用 file_id 调用下载接口获取文件。"
            return json.dumps(record, ensure_ascii=False)

        except Exception as exc:
            logger.error("CSV 导出失败: %s", exc)
            return f"Error: CSV 导出失败 - {exc}"
        finally:
            if engine is not None:
                engine.dispose()

    return export_to_csv
