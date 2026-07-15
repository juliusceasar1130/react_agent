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
        assert "messages" in result
        assert "lexicon_context" in result
        
        # Verify correct DDL was formatted
        sys_msg = result["messages"][0]
        assert isinstance(sys_msg, SystemMessage)
        assert "CREATE TABLE dim_test_table" in sys_msg.content
