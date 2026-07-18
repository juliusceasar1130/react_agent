# backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage
from backend.app.agent.middleware.rag_middleware import BusinessRagMiddleware

@pytest.mark.asyncio
async def test_business_rag_middleware_abefore_model():
    mock_retriever = MagicMock()
    
    # Mock the business document retriever returning scored docs
    mock_doc = MagicMock()
    mock_doc.document.metadata = {"term": "TestTerm", "domain": "Logistics"}
    mock_doc.document.page_content = "Test content text"
    mock_doc.score = 0.9
    mock_retriever.retrieve = MagicMock(return_value=[mock_doc])
    
    # Mock the db connection
    mock_db = MagicMock()
    mock_db._custom_table_info = {
        "dim_test_table": "CREATE TABLE dim_test_table (col INT);",
        "dim_value_table": "CREATE TABLE dim_value_table (val VARCHAR);"
    }
    
    # Patch the reference inside rag_middleware.py to prevent connecting to Milvus during testing
    with patch("backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever") as mock_lexicon_class:
        mock_lexicon_retriever = AsyncMock()
        mock_lexicon_class.return_value = mock_lexicon_retriever
        
        middleware = BusinessRagMiddleware(
            retriever=mock_retriever,
            doc_k=1,
            db=mock_db
        )
        
        # 1. 模拟三层检索结果：
        # - 表结构检索命中了 dim_test_table
        # - 值层命中了 dim_value_table (触发辅助表追加)
        # - 行层命中了 dim_row_table (不应触发辅助表追加)
        mock_table = MagicMock()
        mock_table.score = 0.95
        mock_table.node.metadata = {"table_name": "dim.dim_test_table"}
        mock_table.node.text = "表: dim.dim_test_table\n说明: 维度测试表"
        
        mock_value = MagicMock()
        mock_value.score = 0.92
        mock_value.node.metadata = {"table_name": "dim.dim_value_table", "column_name": "val", "exact_value": "test_val"}
        
        mock_row = MagicMock()
        mock_row.score = 0.88
        mock_row.node.metadata = {"table_name": "dim.dim_row_table", "primary_key_column": "id", "primary_key_val": "10"}
        
        mock_lexicon_retriever.retrieve_all.return_value = {
            "tables": [mock_table],
            "values": [mock_value],
            "rows": [mock_row]
        }
        
        # Call abefore_model
        state = {"messages": [HumanMessage(content="查询测试")]}
        runtime = MagicMock()
        
        result = await middleware.abefore_model(state, runtime)
        assert result is not None
        assert "messages" not in result
        assert "lexicon_context" in result
        
        formatted_text = result["lexicon_context"]["formatted_text"]
        
        # 校验：主表结构标题与内容正确
        assert "### 2.1 命中的主要数据库表结构 (Primary Table Schema)" in formatted_text
        assert "表: dim.dim_test_table" in formatted_text
        assert "说明: 维度测试表" in formatted_text
        
        # 校验：列值检索出来的表，下降为辅助参考表且标题和内容正确
        assert "### 2.1.1 辅助参考的数据库表结构 (Auxiliary Table Schema)" in formatted_text
        assert "CREATE TABLE dim_value_table" in formatted_text
        
        # 校验：行检索命中的表 (dim_row_table) 不应当在 Schema 板块被追加
        assert "dim_row_table" not in formatted_text.split("### 2.2")[0]
        
        # 校验新增加的结构化 detail 明细
        assert "detail" in result["lexicon_context"]
        detail = result["lexicon_context"]["detail"]
        assert "tables" in detail
        assert len(detail["tables"]) == 2  # 1个主表 + 1个辅助表
        assert detail["tables"][0]["table_name"] == "dim.dim_test_table"
        assert detail["tables"][1]["table_name"] == "dim.dim_value_table"
