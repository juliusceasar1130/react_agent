# backend/app/agent/tools/csv_export_tool.py
"""
CSV 导出工具

当 SQL 查询结果超过系统硬限制（被截断）时，Agent 可调用此工具
将完整查询结果导出为 CSV 文件供用户下载，全程不经过 LLM 上下文。

修改时间: 2026-08-18 Asia/Shanghai
主要修改内容:
- 接入统一 ArtifactStore 单例进行工件持久化与生命周期管理
- 解除对 SqlSubAgentState 的硬绑定，升级为 ToolRuntime[RequestContext, Any] 适配主子智能体
- required_skill 改为可选参数
"""

import csv
import json
import logging
from datetime import datetime
from typing import Any

from langchain.tools import ToolRuntime, tool as langchain_tool
from langchain_core.tools import ToolException
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent.context import RequestContext
from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from backend.app.agent.utils import emit_stream_status
from backend.app.artifacts import get_artifact_store
from backend.app.config import settings

logger = logging.getLogger(__name__)


class ExportToCsvInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        description="Read-only SQL SELECT query to execute and export to a CSV file."
    )


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

    @langchain_tool(args_schema=ExportToCsvInput)
    def export_to_csv(
        query: str,
        runtime: ToolRuntime[RequestContext, Any],
    ) -> Any:
        """
        Execute a SQL query and export the full results to a CSV file for user download.

        Use this tool ONLY when:
        1. The sql_db_query tool reports that results were truncated due to the system hard limit, and the user needs the complete dataset; OR
        2. The user explicitly requests exporting/downloading query data to a CSV file.

        This tool saves results directly to a server-side CSV file without loading rows into LLM context.

        Args:
            query: A valid SQL SELECT query string to execute and export.
        """

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

            store = get_artifact_store()
            export_dir = store.exports_dir
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

            caller_role = "sql_domain_agent"
            if runtime:
                if hasattr(runtime, "subagent_name") and runtime.subagent_name:
                    caller_role = str(runtime.subagent_name)
                else:
                    cfg = getattr(runtime, "config", None) or {}
                    if isinstance(cfg, dict):
                        meta = cfg.get("metadata", {})
                        conf = cfg.get("configurable", {})
                        caller_role = meta.get("subagent_name") or conf.get("subagent_name") or meta.get("agent_name") or "sql_domain_agent"
            tool_call_id_str = (
                str(runtime.tool_call_id)
                if runtime and hasattr(runtime, "tool_call_id") and runtime.tool_call_id
                else "call_unknown"
            )

            handle = store.save_export_file(
                source_file_path=filepath,
                filename=filename,
                media_type="text/csv",
                row_count=row_count,
                col_count=col_count,
                columns=columns,
                tool_call_id=tool_call_id_str,
                created_by=caller_role,
            )

            file_size_kb = (handle.extra.get("size_bytes", 0) if handle.extra else 0) / 1024

            logger.info(
                "CSV 导出成功: %s (%d 行, %d 列, %.1f KB), file_id=%s",
                filepath, row_count, col_count, file_size_kb, handle.artifact_id,
            )
            emit_stream_status(
                "CSV 导出完成",
                stage="writing",
                source="export_to_csv",
            )

            # 过滤掉 stored_path 物理路径，防止大模型上下文和前端 tool_results 泄露
            safe_record = {
                "kind": "file_export",
                "file_id": handle.artifact_id,
                "filename": filename,
                "row_count": row_count,
                "col_count": col_count,
                "columns": columns,
                "size_bytes": handle.extra.get("size_bytes", 0) if handle.extra else 0,
                "created_at": handle.created_at,
                "expires_at": handle.expires_at,
                "download_url": handle.download_url,
            }

            # 同时返回 messages 与 tool_artifact 用于流式直推
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=json.dumps(safe_record, ensure_ascii=False),
                        tool_call_id=tool_call_id_str,
                    )
                ],
                "tool_artifact": {
                    "kind": "file_export",
                    "tool_call_id": tool_call_id_str,
                    "file_id": handle.artifact_id,
                    "filename": filename,
                    "row_count": row_count,
                    "col_count": col_count,
                    "columns": columns,
                    "size_bytes": handle.extra.get("size_bytes", 0) if handle.extra else 0,
                    "expires_at": handle.expires_at,
                },
            })

        except SQLLintException as exc:
            logger.warning(f"export_to_csv 校验未通过拦截: {exc}")
            raise ToolException(str(exc))
        except ToolException:
            raise
        except Exception as exc:
            logger.error("CSV 导出失败: %s", exc)
            raise ToolException(f"Error: CSV 导出失败 - {exc}")

    export_to_csv.handle_tool_error = True
    return export_to_csv
