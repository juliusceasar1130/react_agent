# backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py
import pytest
from pymilvus import connections, utility, Collection
from backend.app.config import settings
from backend.app.agent.vector.sql_lexicon.tasks import run_metadata_lexicon_sync

def test_metadata_lexicon_synchronization():
    # 1. 运行同步程序
    run_metadata_lexicon_sync(overwrite=True)
    
    # 2. 提取 host & port
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
        col = Collection(name)
        col.flush()
        num_entities = col.num_entities
        print(f"Collection {name} contains {num_entities} entities.")
        assert num_entities > 0
        
    connections.disconnect("default")
