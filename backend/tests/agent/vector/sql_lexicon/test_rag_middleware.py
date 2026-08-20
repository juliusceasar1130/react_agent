# backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import HumanMessage
from backend.app.agent.middleware.rag_middleware import BusinessRagMiddleware
from backend.app.agent.context import RequestContext

@pytest.mark.asyncio
async def test_business_rag_middleware_abefore_model():
    mock_retriever = MagicMock()
    
    # Mock the business document retriever returning scored docs
    mock_doc = MagicMock()
    mock_doc.document.metadata = {"term": "TestTerm", "domain": "Logistics"}
    mock_doc.document.page_content = "Test content text"
    mock_doc.score = 0.9
    mock_retriever.aretrieve = AsyncMock(return_value=[mock_doc])
    
    # Mock the db connection
    mock_db = MagicMock()
    mock_db._custom_table_info = {
        "dim.dim_test_table": "CREATE TABLE dim_test_table (col INT);",
        "dim.dim_value_table": "CREATE TABLE dim_value_table (val VARCHAR);"
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
        # - 表结构检索命中了 dim.dim_test_table
        # - 值层命中了 dim.dim_value_table (触发辅助表追加)
        # - 行层命中了 dim.dim_row_table (不应触发辅助表追加)
        mock_table = MagicMock()
        mock_table.score = 0.95
        mock_table.node.metadata = {"table_name": "dim.dim_test_table"}
        mock_table.node.text = "表: dim.dim_test_table\n说明: 维度测试表"
        
        mock_value = MagicMock()
        mock_value.score = 0.92
        mock_value.node.metadata = {"table_name": "dim.dim_value_table", "column_name": "val", "exact_value": "test_val"}
        mock_value.node.text = "值: test_val"
        
        mock_row = MagicMock()
        mock_row.score = 0.88
        mock_row.node.metadata = {"table_name": "dim.dim_row_table", "primary_key_column": "id", "primary_key_val": "10"}
        mock_row.node.text = "行: id=10"
        
        mock_lexicon_retriever.retrieve_all.return_value = {
            "tables": [mock_table],
            "values": [mock_value],
            "rows": [mock_row]
        }
        
        # Call abefore_model with runtime.context (Context API)
        state = {"messages": [HumanMessage(content="查询测试")]}
        runtime = MagicMock()
        runtime.context = RequestContext(
            lexicon_context=None,
            rag_context=[],
            rag_query="",
        )
        
        result = await middleware.abefore_model(state, runtime)
        # Phase 1 契约: abefore_model 写入 runtime.context 并返回 None (0 字节入 State)
        assert result is None
        assert runtime.context["lexicon_context"] is not None
        
        formatted_text = runtime.context["lexicon_context"]["formatted_text"]
        
        # 校验：主表结构标题与内容正确
        assert "### 2.1 业务核心数据表结构定义 (Table DDL & Column Comments)" in formatted_text
        assert "CREATE TABLE dim_test_table" in formatted_text
        assert "CREATE TABLE dim_value_table" in formatted_text
        
        # 校验：行检索命中的表 (dim.dim_row_table) 不应当在 Schema 板块被追加
        assert "dim.dim_row_table" not in formatted_text.split("### 2.2")[0]
        
        # 校验结构化 detail 明细
        assert "detail" in runtime.context["lexicon_context"]
        detail = runtime.context["lexicon_context"]["detail"]
        assert "tables" in detail
        assert len(detail["tables"]) == 2  # 1个主表 + 1个辅助表
        assert detail["tables"][0]["table_name"] == "dim.dim_test_table"
        assert detail["tables"][1]["table_name"] == "dim.dim_value_table"

        # 2. 测试二次调用 (同一 Turn 内相同 query 与已有 lexicon_context)：应直接跳过 RAG 检索返回 None
        second_result = await middleware.abefore_model(state, runtime)
        assert second_result is None


@pytest.mark.asyncio
async def test_business_rag_middleware_exception_handling():
    """测试 3: 当 RAG 检索抛出异常时，仍更新 context.rag_query 并将 lexicon_context 置为空，防止同 Turn 内循环重试"""
    mock_retriever = MagicMock()
    mock_retriever.aretrieve = AsyncMock(side_effect=RuntimeError("Milvus connection failed"))

    middleware = BusinessRagMiddleware(
        retriever=mock_retriever,
        doc_k=1,
    )
    state = {"messages": [HumanMessage(content="异常测试")]}
    runtime = MagicMock()
    runtime.context = RequestContext(
        lexicon_context=None,
        rag_context=[],
        rag_query="",
    )

    result = await middleware.abefore_model(state, runtime)
    assert result is None
    assert runtime.context["rag_query"] == "异常测试"
    assert runtime.context["lexicon_context"] is None
    assert runtime.context["rag_context"] == []
