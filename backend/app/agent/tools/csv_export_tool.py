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
from langchain_core.tools import ToolException
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from backend.app.agent.utils import emit_stream_status
from backend.app.export_files import create_export_record, get_export_dir
from backend.app.config import settings

logger = logging.getLogger(__name__)


def create_csv_export_tool(
    engine: Engine,
    custom_table_info: dict = None,
) -> Any:
    """
    创建 CSV 导出工具。

    Args:
        engine: 数据库连接引擎
        custom_table_info: 数据库 DDL 字典，供 SQL Linter 使用

    Returns:
        export_to_csv 工具实例
    """

    @langchain_tool
    def export_to_csv(query: str, required_skill: str, runtime: ToolRuntime) -> Command:
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
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            raise ToolException(
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再导出数据。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。"
            )

        try:
            emit_stream_status(
                "正在执行 SQL 合规检查",
                stage="querying",
                source="export_to_csv",
            )
            validate_readonly_query(query, custom_table_info)

            emit_stream_status(
                "正在导出完整 CSV 文件",
                stage="querying",
                source="export_to_csv",
            )

            export_dir = get_export_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"
            filepath = export_dir / filename

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

            # 行数安全上限校验 (OOM Limit Guard)
            max_rows = settings.sql_export_max_rows
            if row_count > max_rows:
                if filepath.exists():
                    filepath.unlink()
                raise ToolException(
                    f"Error: 导出结果行数 ({row_count:,} 行) 超过系统安全上限 ({max_rows:,} 行)。"
                    f"为防内存溢出崩溃，执行已被强行终止。请增加过滤范围或使用聚合统计重试。"
                )

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

            # 过滤掉 stored_path 物理路径，防止大模型上下文和前端 tool_results 泄露
            safe_record = {k: v for k, v in record.items() if k != "stored_path"}

            # 同时返回 messages 与 tool_artifact 用于流式直推
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=json.dumps(safe_record, ensure_ascii=False),
                        tool_call_id=str(runtime.tool_call_id) if runtime and hasattr(runtime, "tool_call_id") else "call_unknown",
                    )
                ],
                "tool_artifact": {
                    "kind": "file_export",
                    "file_id": record["file_id"],
                    "filename": filename,
                    "row_count": row_count,
                    "col_count": col_count,
                    "columns": columns,
                    "size_bytes": record.get("size_bytes", 0),
                    "expires_at": record.get("expires_at", "")
                },
            })

        except SQLLintException as exc:
            logger.warning(f"export_to_csv 校验未通过拦截: {exc}")
            raise ToolException(str(exc))
        except Exception as exc:
            logger.error("CSV 导出失败: %s", exc)
            raise ToolException(f"Error: CSV 导出失败 - {exc}")

    export_to_csv.handle_tool_error = True
    return export_to_csv
