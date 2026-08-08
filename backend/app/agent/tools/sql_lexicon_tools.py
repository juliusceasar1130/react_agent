# backend/app/agent/tools/sql_lexicon_tools.py
import logging
import re
from typing import Any

from langchain_core.tools import tool as langchain_tool

from backend.app.agent.utils import emit_stream_status
from backend.app.config import settings

logger = logging.getLogger(__name__)


def create_db_value_lexicon_tool(lexicon_retriever: Any) -> Any:
    """
    创建列值语义纠偏工具。
    """

    @langchain_tool
    def search_db_value_lexicon(query: str, limit: int = 10) -> str:
        """
        通过语义相似度在去重列值字典中检索数据库字段物理真实值。
        
        当你发现 SQL 执行结果为空 (Empty Result)，怀疑是过滤条件值拼写、别名、或别称不匹配时调用。
        例如：用户问“电泳二期”，若数据库实际存“前道电泳二区”，使用此工具做模糊匹配可以找到正确值。
        
        Args:
            query: 待检索列值的模糊文本或关键字。
            limit: 返回的最大匹配结果数量。默认值为 10，当怀疑有更多匹配值时，可传入更大的数值。
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
        
        当你需要根据模糊实体名/属性（如某个特定的设备名称、工位别名）定位表中的主键 ID 时调用。
        
        Args:
            query: 待检索行实体（如工位、工艺区域、设备等）的名称或别名。
            limit: 返回的最大匹配结果数量。默认值为 10，当怀疑有更多匹配值时，可传入更大的数值。
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
        
        当你对某张表的字段名、字段类型不确定，或者遇到 SQL 报错（如列不存在）时调用。
        
        Args:
            query: 与目标表相关的自然语言描述。
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
                
                # 剥离注释中的样本数据
                clean_ddl = re.sub(r"-- \d+\. \{.*?\}", "", ddl, flags=re.DOTALL).strip()
                clean_ddl = re.sub(r"VARCHAR\(\d+\)", "VARCHAR", clean_ddl, flags=re.IGNORECASE)
                
                lines.append(f"### 表: {t_name} (相似度得分: {score:.4f})")
                lines.append(f"```sql\n{clean_ddl}\n```\n")
                
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error retrieving table schema lexicon: {e}", exc_info=True)
            return f"Error retrieving table schema lexicon: {str(e)}"

    return search_db_table_schema
