# backend/app/agent/tools/csv_export_tool.py
"""
CSV 导出工具

当 SQL 查询结果超过系统硬限制（被截断）时，Agent 可调用此工具
将完整查询结果导出为 CSV 文件供用户下载，全程不经过 LLM 上下文。
"""

import csv
import logging
import os
import re
import tempfile
from datetime import datetime
from typing import Any, Optional

from langchain.tools import ToolRuntime, tool as langchain_tool
from sqlalchemy import create_engine, text

from backend.app.agent.tools.sql_tools import FORBIDDEN_SQL_PATTERN
from backend.app.config import settings

logger = logging.getLogger(__name__)

# CSV 导出的默认目录，使用系统的临时文件夹以方便系统自动清理，避免长期占用大量磁盘空间
CSV_EXPORT_DIR = os.path.join(tempfile.gettempdir(), "sql_agent_exports")


def create_csv_export_tool(db_uri: str) -> Any:
    """
    创建 CSV 导出工具。

    Args:
        db_uri: 数据库连接 URI

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
        # 0. 安全性拦截：与 sql_db_query 保持一致
        if FORBIDDEN_SQL_PATTERN.search(query):
            logger.warning(f"CSV 导出安全拦截：检测到危险 SQL 关键字。Query: {query}")
            return (
                "Error: 严重安全警告 - 该操作已被系统拦截。\n"
                "export_to_csv 仅允许执行只读查询 (SELECT)，禁止执行任何修改操作。"
            )

        # 1. 技能加载校验
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再导出数据。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。"
            )

        try:
            # 2. 准备导出环境：确保临时存储目录已创建
            os.makedirs(CSV_EXPORT_DIR, exist_ok=True)

            # 3. 构造唯一文件名：使用时间戳防止并发导出时的文件冲突
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"
            filepath = os.path.join(CSV_EXPORT_DIR, filename)

            # 4. 数据库读取逻辑：使用 SQLAlchemy Engine 直接拉取完整结果集
            # 这种方式不占用 LangGraph 的状态内存，也不涉及 LLM 的 Token 消耗
            engine = create_engine(db_uri)
            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns = list(result.keys()) # 提取列名作为 CSV 表头
                rows = result.fetchall()      # 拉取所有行

            # 5. 文件写入逻辑：使用 utf-8-sig 编码以兼容 Windows Excel 直接打开不乱码
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(columns)  # 写入首行表头
                for row in rows:
                    writer.writerow(row)

            # 6. 元数据收集：用于向 Agent 反馈导出结果统计
            row_count = len(rows)
            col_count = len(columns)
            file_size_kb = os.path.getsize(filepath) / 1024

            logger.info(
                "CSV 导出成功: %s (%d 行, %d 列, %.1f KB)",
                filepath, row_count, col_count, file_size_kb,
            )

            # 释放连接池资源
            engine.dispose()

            # 返回给 Agent 的结果：仅包含路径和统计信息，不包含任何数据内容
            return (
                f"✅ CSV 导出成功！\n"
                f"- 文件路径: {filepath}\n"
                f"- 数据量: {row_count} 行 × {col_count} 列\n"
                f"- 文件大小: {file_size_kb:.1f} KB\n"
                f"- 列名: {', '.join(columns)}\n\n"
                f"请告知用户文件已导出，可以到上述路径下载。"
            )

        except Exception as exc:
            logger.error("CSV 导出失败: %s", exc)
            return f"Error: CSV 导出失败 - {exc}"

    return export_to_csv
