# backend/tests/agent/vector/sql_lexicon/test_init_collections.py
import pytest
from pymilvus import connections, utility
from backend.app.config import settings
from backend.app.agent.vector.sql_lexicon.init_script import main as run_init

@pytest.mark.asyncio
async def test_milvus_collections_initialization():
    # 1. 运行物理创建
    await run_init()
    
    # 2. 从 settings.milvus_uri 提取 host & port
    uri = settings.milvus_uri.replace("http://", "").replace("https://", "")
    host = "localhost"
    port = "19530"
    if ":" in uri:
        parts = uri.split(":")
        host = parts[0]
        port = parts[1].split("/")[0] if "/" in parts[1] else parts[1]
    
    connections.connect("default", host=host, port=port)
    
    expected_collections = ["table_schema_store", "db_value_lexicon", "db_row_lexicon"]
    for name in expected_collections:
        assert utility.has_collection(name) is True
        
    connections.disconnect("default")
