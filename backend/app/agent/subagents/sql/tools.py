# backend/app/agent/subagents/sql/tools.py
"""
SQL 子智能体专用工具工厂集合

聚合 SQL 查询包装工具、历史样例检索工具以及数据库物理词典（值/行/表结构）探索工具。
"""

import logging
import re
import json
import ast
import datetime
from decimal import Decimal
from typing import Any, List, Optional, Union

import sqlglot
from langchain.tools import ToolRuntime, tool as langchain_tool
from langchain_core.tools import ToolException
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from backend.app.agent.context import RequestContext
from backend.app.agent.state import SqlSubAgentState
from backend.app.agent.utils.sql_linter import validate_readonly_query, SQLLintException
from backend.app.agent.constants import SQL_ERROR_KEYWORDS
from backend.app.agent.utils import emit_stream_status
from backend.app.agent.vector.base import BaseRetriever
from backend.app.config import settings

logger = logging.getLogger(__name__)


def _extract_table_names(query: str) -> set[str]:
    """
    使用 sqlglot AST 精确提取 SQL 中涉及的所有表名。
    能正确处理：CTE、子查询、多表 JOIN、schema 限定名（schema.table）、表别名等。
    解析失败时返回空集合，调用方应按保守策略处理。
    """
    try:
        tables = set()
        parsed = sqlglot.parse_one(query, error_level=sqlglot.ErrorLevel.IGNORE)
        for table in parsed.find_all(sqlglot.exp.Table):
            tables.add(table.name.lower())
        return tables
    except Exception:
        return set()


def _is_pure_dimension_query(query: str) -> bool:
    """
    判断当前查询是否仅涉及维度表/字典表（不含任何事实表）。
    基于 sqlglot AST 精确提取所有涉及的表名后与白名单比对。
    """
    involved_tables = _extract_table_names(query)
    if not involved_tables:
        return False

    dim_whitelist = settings.dimension_tables
    if not dim_whitelist:
        return False

    return involved_tables.issubset(dim_whitelist)


def create_wrapped_query_tool(
    original_query_tool: Any,
    original_checker_tool: Optional[Any] = None,
    custom_table_info: Optional[dict] = None,
) -> Any:
    """
    创建包装后的 SQL 查询工具
    """

    @langchain_tool
    def sql_db_query(query: str, required_skill: str, runtime: ToolRuntime[RequestContext, SqlSubAgentState]) -> str:
        """
        Execute a SQL query against the database and return results.

        IMPORTANT: You must specify the 'required_skill' parameter with the exact skill name
        that this query depends on (e.g., 'paint_shop_vehicle_logistics'). The skill must have been loaded
        via load_skill() first. If you are switching to a different business domain,
        call load_skill() for the new domain BEFORE calling this tool.

        The query will be automatically validated before execution.
        Results will have dates normalized to ISO 8601 format (YYYY-MM-DD).

        Args:
            query: A valid SQL query string.
            required_skill: The name of the skill/domain this query belongs to.
        """
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再执行查询。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。\n"
                "可用技能请查看系统提示中的 Available Skills 部分。"
            )

        if settings.sql_linter_enabled:
            emit_stream_status(
                "正在执行 SQL 合规检查",
                stage="querying",
                source="sql_db_query",
            )
            db_custom_info = custom_table_info
            if not db_custom_info and hasattr(original_query_tool, "db"):
                db_custom_info = getattr(original_query_tool.db, "_custom_table_info", None) or {}
            
            try:
                validate_readonly_query(query, db_custom_info)
            except SQLLintException as exc:
                raise ToolException(str(exc))

        if settings.sql_checker_mode == "safety" and original_checker_tool is not None:
            emit_stream_status(
                "正在检查 SQL 语法",
                stage="querying",
                source="sql_db_query_checker",
            )
            check_result = original_checker_tool.invoke({"query": query})
            check_result_str = str(check_result).lower()

            if any(err in check_result_str for err in SQL_ERROR_KEYWORDS):
                logger.warning("SQL 语法检查失败: %s", check_result)
                return f"SQL 语法检查失败:\n{check_result}\n请修正查询后重试。"

            logger.debug("SQL 语法检查通过")

        emit_stream_status(
            "正在执行 SQL 查询",
            stage="querying",
            source="sql_db_query",
        )
        if hasattr(original_query_tool, "db") and hasattr(original_query_tool.db, "run_no_throw"):
            raw_result = original_query_tool.db.run_no_throw(
                query,
                include_columns=True,
            )
        else:
            raw_result = original_query_tool.invoke({"query": query})

        emit_stream_status(
            "已收到查询结果，正在整理数据",
            stage="writing",
            source="sql_db_query",
        )

        if isinstance(raw_result, str):
            stripped = raw_result.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    raw_result = ast.literal_eval(stripped)
                except Exception as eval_err:
                    try:
                        raw_result = json.loads(stripped)
                    except Exception:
                        logger.error(
                            "查询结果字符串反序列化彻底失败 (长度=%d), ast.literal_eval 错误: %s",
                            len(stripped), eval_err,
                        )
                        raise ToolException(
                            "Error: 数据库返回结果无法解析为结构化数据，可能包含不支持的类型。"
                            "请尝试简化查询（减少列数或使用 LIMIT 限制行数）后重试。"
                        )

        cleaned_result = []
        if isinstance(raw_result, list):
            for row in raw_result:
                if isinstance(row, dict):
                    cleaned_row = {}
                    for k, v in row.items():
                        if isinstance(v, (datetime.datetime, datetime.date)):
                            cleaned_row[k] = v.isoformat()
                        elif isinstance(v, Decimal):
                            cleaned_row[k] = float(v)
                        else:
                            cleaned_row[k] = v
                    cleaned_result.append(cleaned_row)
                else:
                    cleaned_result.append(row)
        else:
            cleaned_result = raw_result

        is_dim = _is_pure_dimension_query(query)
        hard_limit = (
            settings.dimension_result_hard_limit if is_dim else settings.sql_result_hard_limit
        )
        preview_rows = settings.sql_result_preview_rows
        
        row_count = len(cleaned_result) if isinstance(cleaned_result, list) else 0
        truncated = row_count >= hard_limit

        from datetime import timezone, timedelta
        tz_utc8 = timezone(timedelta(hours=8))
        db_query_time = datetime.datetime.now(tz_utc8).strftime("%Y-%m-%d %H:%M:%S")
        time_prefix = f"[查询时刻: {db_query_time}]\n"

        columns = []
        if cleaned_result and isinstance(cleaned_result, list) and isinstance(cleaned_result[0], dict):
            columns = list(cleaned_result[0].keys())
        else:
            try:
                parsed = sqlglot.parse_one(query)
                columns = [col.alias_or_name for col in parsed.find_all(sqlglot.exp.Column)]
                columns = list(dict.fromkeys(columns))
            except Exception:
                pass

        source_tables = list(_extract_table_names(query))

        if truncated:
            preview_rows_data = cleaned_result[:preview_rows]
            preview_text = json.dumps(preview_rows_data, ensure_ascii=False)
            logger.warning(
                "SQL 查询结果超限截断: 真实行数=%d, 硬限制=%d, 预览行数=%d",
                row_count, hard_limit, preview_rows,
            )
            llm_content = (
                f"{time_prefix}"
                f"⚠️ SYSTEM WARNING: 查询共返回 {row_count} 行结果，达到系统硬限制 ({hard_limit} 行) 并被强制截断。\n"
                f"以下仅展示前 {preview_rows} 行数据预览，基于此数据进行的汇总分析可能不完整或不准确。\n\n"
                f"建议操作：\n"
                f"1. 如果用户需要完整原始数据，请建议使用 export_to_csv 工具导出为 CSV 文件下载。\n"
                f"2. 如果需要统计分析，请改写 SQL 使用 GROUP BY / COUNT / SUM 等聚合函数，让数据库完成计算。\n\n"
                f"数据预览 (前 {preview_rows} 行):\n{preview_text}"
            )
        else:
            logger.debug("SQL 查询结果未超限 (真实行数=%d), 全量返回", row_count)
            llm_content = f"{time_prefix}{json.dumps(cleaned_result, ensure_ascii=False)}"

        rows_for_sse = cleaned_result[:hard_limit] if isinstance(cleaned_result, list) else []

        return Command(update={
            "messages": [
                ToolMessage(
                    content=llm_content,
                    tool_call_id=str(runtime.tool_call_id) if hasattr(runtime, "tool_call_id") else "call_unknown",
                )
            ],
            "tool_artifact": {
                "kind": "query_result",
                "tool_call_id": str(runtime.tool_call_id) if hasattr(runtime, "tool_call_id") else None,
                "columns": columns,
                "rows": rows_for_sse,
                "row_count": row_count,
                "truncated": truncated,
                "query_time": db_query_time,
                "source_tables": source_tables,
            }
        })

    sql_db_query.handle_tool_error = True
    return sql_db_query


def create_sql_example_search_tool(
    retriever: BaseRetriever,
    *,
    top_k: int = 2,
) -> Any:
    """
    创建 SQL 示例检索工具 search_saved_correct_tool_uses。
    """

    @langchain_tool
    def search_saved_correct_tool_uses(question: str, required_skill: str, runtime: ToolRuntime[RequestContext, SqlSubAgentState]) -> Union[str, List[dict]]:
        """
        根据当前用户问题检索历史 SQL 示例。

        Args:
            question: 当前用户问题的自然语言描述。
            required_skill: 本次检索依赖的技能/业务域名称，必须与 sql_db_query 的 required_skill 保持一致。
        """
        skills_loaded = runtime.state.get("skills_loaded", [])
        if required_skill not in skills_loaded:
            return (
                f"Error: 请先使用 load_skill('{required_skill}') 加载该业务技能后再检索 SQL 示例。\n"
                f"当前已加载的技能: {skills_loaded or '无'}。\n"
                "可用技能请查看系统提示中的 Available Skills 部分。"
            )

        if not question or not question.strip():
            logger.warning("search_saved_correct_tool_uses: 收到空问题，直接返回空列表")
            return []

        try:
            emit_stream_status(
                "正在检索历史 SQL 示例",
                stage="retrieving",
                source="search_saved_correct_tool_uses",
            )
            results = retriever.retrieve(
                query=question,
                k=top_k,
                doc_type="sql_example",
                domain=required_skill,
            )
        except Exception as exc:
            logger.error(
                "search_saved_correct_tool_uses: 检索 SQL 示例时出错，将返回空结果: %s",
                exc,
            )
            return []

        examples: List[dict] = []
        for scored in results:
            doc = scored.document
            metadata = doc.metadata or {}

            sql_text = metadata.get("sql", "")
            if not sql_text:
                tool_args = metadata.get("tool_args") or {}
                if isinstance(tool_args, dict):
                    sql_text = tool_args.get("sql", "") or tool_args.get("query", "")

            examples.append(
                {
                    "question": doc.page_content or metadata.get("question", ""),
                    "sql": sql_text,
                    "description": metadata.get("description", ""),
                    "domain": metadata.get("domain", ""),
                    "score": scored.score,
                }
            )

        logger.info(
            "search_saved_correct_tool_uses: 已检索到 %d 条 SQL 示例（doc_type=sql_example）",
            len(examples),
        )
        return examples

    return search_saved_correct_tool_uses


def create_db_value_lexicon_tool(lexicon_retriever: Any) -> Any:
    """
    创建列值语义纠偏工具。
    """

    @langchain_tool
    def search_db_value_lexicon(query: str, limit: int = 10) -> str:
        """
        通过语义相似度在去重列值字典中检索数据库字段物理真实值。
        """
        if lexicon_retriever is None:
            return "Error: Database lexicon retriever is not initialized or disabled."
        try:
            emit_stream_status(
                f"正在进行列值检索纠偏: {query}",
                stage="retrieving",
                source="search_db_value_lexicon",
            )
            if hasattr(lexicon_retriever, "value_index") and lexicon_retriever.value_index is not None:
                nodes = lexicon_retriever.value_index.as_retriever(vector_store_query_mode="hybrid", similarity_top_k=limit).retrieve(query)
            elif hasattr(lexicon_retriever, "value_retriever"):
                nodes = lexicon_retriever.value_retriever.retrieve(query)
            else:
                nodes = []

            if not nodes:
                return f"未在列值词典中找到与 '{query}' 相关的物理真实值。"
            
            lines = [
                "已找到相似的真实物理列值映射参考：\n",
                "| 数据表 | 目标列名 | 真实物理字段值 (SQL Literal) | 相似度得分 |",
                "| :--- | :--- | :--- | :--- |"
            ]
            for n in nodes[:limit]:
                meta = n.node.metadata
                t_name = meta.get("table_name", "")
                c_name = meta.get("column_name", "")
                val = meta.get("exact_value", "")
                score = getattr(n, "score", 0.0)
                lines.append(f"| `{t_name}` | `{c_name}` | `'{val}'` | {score:.4f} |")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error retrieving value lexicon: {e}", exc_info=True)
            return f"Error retrieving value lexicon: {str(e)}"

    return search_db_value_lexicon


def create_db_row_lexicon_tool(lexicon_retriever: Any) -> Any:
    """
    创建行级实体对齐工具。
    """

    @langchain_tool
    def search_db_row_lexicon(query: str, limit: int = 10) -> str:
        """
        通过语义相似度在行实体字典中检索对应记录的主键及核心属性描述。
        """
        if lexicon_retriever is None:
            return "Error: Database lexicon retriever is not initialized or disabled."
        try:
            emit_stream_status(
                f"正在进行行级实体检索对齐: {query}",
                stage="retrieving",
                source="search_db_row_lexicon",
            )
            if hasattr(lexicon_retriever, "row_index") and lexicon_retriever.row_index is not None:
                nodes = lexicon_retriever.row_index.as_retriever(vector_store_query_mode="hybrid", similarity_top_k=limit).retrieve(query)
            elif hasattr(lexicon_retriever, "row_retriever"):
                nodes = lexicon_retriever.row_retriever.retrieve(query)
            else:
                nodes = []

            if not nodes:
                return f"未在行实体词典中找到与 '{query}' 相关的记录。"
            
            lines = [
                "已找到相似的数据库行记录映射参考：\n",
                "| 数据表 | 主键列 | 真实主键值 | 关联行核心属性描述 | 相似度得分 |",
                "| :--- | :--- | :--- | :--- | :--- |"
            ]
            for n in nodes[:limit]:
                meta = n.node.metadata
                t_name = meta.get("table_name", "")
                pk_col = meta.get("primary_key_column", "")
                pk_val = meta.get("primary_key_val", "")
                row_content = meta.get("row_content", "")
                score = getattr(n, "score", 0.0)
                lines.append(f"| `{t_name}` | `{pk_col}` | `'{pk_val}'` | {row_content} | {score:.4f} |")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error retrieving row lexicon: {e}", exc_info=True)
            return f"Error retrieving row lexicon: {str(e)}"

    return search_db_row_lexicon


def create_db_table_schema_tool(lexicon_retriever: Any) -> Any:
    """
    创建表结构补充探索工具。
    """

    @langchain_tool
    def search_db_table_schema(query: str, limit: int = 5) -> str:
        """
        通过语义相似度在表结构字典中检索最相关的 DDL 表定义详情。
        """
        if lexicon_retriever is None:
            return "Error: Database lexicon retriever is not initialized or disabled."
        try:
            emit_stream_status(
                f"正在进行表结构 DDL 检索: {query}",
                stage="retrieving",
                source="search_db_table_schema",
            )
            if hasattr(lexicon_retriever, "schema_index") and lexicon_retriever.schema_index is not None:
                nodes = lexicon_retriever.schema_index.as_retriever(vector_store_query_mode="hybrid", similarity_top_k=limit).retrieve(query)
            elif hasattr(lexicon_retriever, "schema_retriever"):
                nodes = lexicon_retriever.schema_retriever.retrieve(query)
            else:
                nodes = []
            if not nodes:
                return f"未找到与 '{query}' 相关的表结构定义。"
            
            lines = ["已找到以下最相关的表 DDL 定义：\n"]
            for n in nodes[:limit]:
                meta = n.node.metadata
                t_name = meta.get("table_name", "")
                score = getattr(n, "score", 0.0)
                ddl = n.node.text
                
                clean_ddl = re.sub(r"-- \d+\. \{.*?\}", "", ddl, flags=re.DOTALL).strip()
                clean_ddl = re.sub(r"VARCHAR\(\d+\)", "VARCHAR", clean_ddl, flags=re.IGNORECASE)
                
                lines.append(f"### 表: {t_name} (相似度得分: {score:.4f})")
                lines.append(f"```sql\n{clean_ddl}\n```\n")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error retrieving table schema lexicon: {e}", exc_info=True)
            return f"Error retrieving table schema lexicon: {str(e)}"

    return search_db_table_schema
