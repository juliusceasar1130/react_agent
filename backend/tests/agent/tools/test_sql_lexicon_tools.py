# backend/tests/agent/tools/test_sql_lexicon_tools.py
import pytest
from unittest.mock import MagicMock

from backend.app.agent.subagents.sql.tools import (
    create_db_value_lexicon_tool,
    create_db_row_lexicon_tool,
    create_db_table_schema_tool,
)


def test_db_value_lexicon_tool():
    # 1. Mock 物理词典检索器及其 index 对象
    mock_retriever = MagicMock()
    mock_node = MagicMock()
    mock_node.node.metadata = {
        "table_name": "dim.dim_process_area",
        "column_name": "process_area_name",
        "exact_value": "前道电泳二区"
    }
    mock_node.score = 0.9532
    
    mock_sub_retriever = MagicMock()
    mock_sub_retriever.retrieve.return_value = [mock_node]
    mock_retriever.value_index.as_retriever.return_value = mock_sub_retriever

    # 2. 实例化并运行工具
    tool = create_db_value_lexicon_tool(mock_retriever)
    result = tool.run({"query": "电泳二期", "limit": 8})

    # 3. 断言验证 Markdown 格式输出与参数纯净性
    assert "| 数据表 | 目标列名 | 真实物理字段值 (SQL Literal) | 相似度得分 |" in result
    assert "`dim.dim_process_area`" in result
    assert "`process_area_name`" in result
    assert "`'前道电泳二区'`" in result
    assert "0.9532" in result
    mock_retriever.value_index.as_retriever.assert_called_once_with(vector_store_query_mode="hybrid", similarity_top_k=8)
    mock_sub_retriever.retrieve.assert_called_once_with("电泳二期")


def test_db_row_lexicon_tool():
    # 1. Mock
    mock_retriever = MagicMock()
    mock_node = MagicMock()
    mock_node.node.metadata = {
        "table_name": "dim.dim_process_area",
        "primary_key_column": "id",
        "primary_key_val": "1002",
        "row_content": "area_name=前道电泳二区"
    }
    mock_node.score = 0.9248
    
    mock_sub_retriever = MagicMock()
    mock_sub_retriever.retrieve.return_value = [mock_node]
    mock_retriever.row_index.as_retriever.return_value = mock_sub_retriever

    # 2. 运行工具
    tool = create_db_row_lexicon_tool(mock_retriever)
    result = tool.run({"query": "前道电泳二区", "limit": 12})

    # 3. 断言验证
    assert "| 数据表 | 主键列 | 真实主键值 | 关联行核心属性描述 | 相似度得分 |" in result
    assert "`dim.dim_process_area`" in result
    assert "`id`" in result
    assert "`'1002'`" in result
    assert "area_name=前道电泳二区" in result
    assert "0.9248" in result
    mock_retriever.row_index.as_retriever.assert_called_once_with(vector_store_query_mode="hybrid", similarity_top_k=12)
    mock_sub_retriever.retrieve.assert_called_once_with("前道电泳二区")


def test_db_table_schema_tool():
    # 1. Mock
    mock_retriever = MagicMock()
    mock_node = MagicMock()
    mock_node.node.metadata = {
        "table_name": "dim.dim_process_area"
    }
    mock_node.node.text = (
        "CREATE TABLE dim.dim_process_area (\n"
        "  id INTEGER,\n"
        "  process_area_name VARCHAR(50)\n"
        ");\n"
        "-- 1. {'id': 1, 'process_area_name': '电泳一区'}"
    )
    mock_node.score = 0.8876
    
    mock_sub_retriever = MagicMock()
    mock_sub_retriever.retrieve.return_value = [mock_node]
    mock_retriever.schema_index.as_retriever.return_value = mock_sub_retriever

    # 2. 运行工具
    tool = create_db_table_schema_tool(mock_retriever)
    result = tool.run({"query": "工艺区域表"})

    # 3. 断言验证样本行剥离与 VARCHAR 规范化
    assert "### 表: dim.dim_process_area (相似度得分: 0.8876)" in result
    assert "VARCHAR" in result
    assert "VARCHAR(50)" not in result
    assert "-- 1." not in result
    assert "CREATE TABLE dim.dim_process_area" in result
