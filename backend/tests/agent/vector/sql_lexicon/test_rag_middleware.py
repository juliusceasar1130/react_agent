# backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage, SystemMessage
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
    mock_db._custom_table_info = {"dim_test_table": "CREATE TABLE dim_test_table (col INT);"}
    
    # Patch the reference inside rag_middleware.py to prevent connecting to Milvus during testing
    with patch("backend.app.agent.middleware.rag_middleware.DatabaseLexiconRetriever") as mock_lexicon_class:
        mock_lexicon_retriever = AsyncMock()
        mock_lexicon_class.return_value = mock_lexicon_retriever
        
        middleware = BusinessRagMiddleware(
            retriever=mock_retriever,
            doc_k=1,
            db=mock_db
        )
        
        # Configure mock retrieval results
        mock_table = MagicMock()
        mock_table.score = 0.95
        mock_table.node.metadata = {"table_name": "dim.dim_test_table"}
        mock_table.node.text = "表: dim.dim_test_table\n说明: 维度测试表\n字段: col(整数列)"
        mock_lexicon_retriever.retrieve_all.return_value = {
            "tables": [mock_table],
            "values": [],
            "rows": []
        }
        
        # Call abefore_model
        state = {"messages": [HumanMessage(content="查询测试")]}
        runtime = MagicMock()
        
        result = await middleware.abefore_model(state, runtime)
        assert result is not None
        assert "messages" not in result
        assert "lexicon_context" in result
        assert "formatted_text" in result["lexicon_context"]
        assert "表: dim.dim_test_table" in result["lexicon_context"]["formatted_text"]
        assert "字段: col(整数列)" in result["lexicon_context"]["formatted_text"]
        
        # 校验新增加的结构化 detail 明细
        assert "detail" in result["lexicon_context"]
        detail = result["lexicon_context"]["detail"]
        assert "tables" in detail
        assert len(detail["tables"]) == 1
        assert detail["tables"][0]["table_name"] == "dim.dim_test_table"
        assert "表: dim.dim_test_table" in detail["tables"][0]["ddl"]
        assert "字段: col(整数列)" in detail["tables"][0]["ddl"]
