# backend/tests/agent/vector/sql_lexicon/test_retriever.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@patch("backend.app.agent.vector.sql_lexicon.retriever.get_milvus_vector_store")
@patch("backend.app.agent.vector.sql_lexicon.retriever.VectorStoreIndex")
@pytest.mark.asyncio
async def test_database_lexicon_retriever_retrieve_all(mock_vector_store_index, mock_get_store):
    # Setup index and retriever mocks
    mock_index = MagicMock()
    mock_retriever = AsyncMock()
    mock_vector_store_index.from_vector_store.return_value = mock_index
    mock_index.as_retriever.return_value = mock_retriever
    
    # Mock node results
    mock_node = MagicMock()
    mock_node.node.text = "test_text"
    mock_node.score = 0.95
    mock_node.node.metadata = {
        "table_name": "dim.dim_test_table", 
        "column_name": "test_col", 
        "exact_value": "val1"
    }
    mock_retriever.aretrieve.return_value = [mock_node]
    
    from backend.app.agent.vector.sql_lexicon.retriever import DatabaseLexiconRetriever
    
    retriever = DatabaseLexiconRetriever()
    
    # Trigger parallel retrieval
    results = await retriever.retrieve_all("test_query")
    
    # Assert correctness
    assert "tables" in results
    assert "values" in results
    assert "rows" in results
    assert len(results["tables"]) == 1
    assert results["tables"][0].score == 0.95
    
    # Verify mock calls
    assert mock_retriever.aretrieve.call_count == 3
