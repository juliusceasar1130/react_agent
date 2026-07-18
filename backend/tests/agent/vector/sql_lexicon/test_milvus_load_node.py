# backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py
from unittest.mock import patch, MagicMock

from llama_index.core.schema import TextNode
from backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node import MilvusIngestionNode


def _make_settings():
    s = MagicMock()
    s.milvus_uri = "http://fake:19530"
    s.milvus_embed_dim = 1024
    s.milvus_rrf_k = 60
    return s


def _make_doc(text, table_name):
    d = MagicMock()
    d.text = text
    d.metadata = {"table_name": table_name}
    return d


@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.VectorStoreIndex")
@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.StorageContext")
@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.get_milvus_vector_store")
def test_ingestion_uses_constructor_nodes_without_chunking(mock_get_store, mock_sc, mock_vs):
    """应直接构造 VectorStoreIndex(nodes=...) 而非 from_documents，节点数等于文档数，均为 TextNode。"""
    mock_sc.from_defaults.return_value = MagicMock()
    docs = [_make_doc("摘要1", "t1"), _make_doc("摘要2", "t2"), _make_doc("摘要3", "t3")]

    node = MilvusIngestionNode(overwrite=True)
    ctx = {"settings": _make_settings(), "schema_docs": docs, "val_docs": [], "row_docs": []}
    node.process(ctx)

    # 直接构造 VectorStoreIndex(nodes=...) 被调用，from_documents 未被调用
    assert mock_vs.called
    assert not mock_vs.from_documents.called

    # 只对非空集合调用（val/row 为空，只调用 1 次）
    assert mock_vs.call_count == 1

    # 从构造参数中提取 nodes 参数
    _, kwargs = mock_vs.call_args
    passed_nodes = kwargs["nodes"]
    assert len(passed_nodes) == 3
    assert all(isinstance(n, TextNode) for n in passed_nodes)
    assert passed_nodes[0].text == "摘要1"


@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.VectorStoreIndex")
@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.StorageContext")
@patch("backend.app.agent.vector.sql_lexicon.pipeline.milvus_load_node.get_milvus_vector_store")
def test_ingestion_skips_empty_collections(mock_get_store, mock_sc, mock_vs):
    """空文档列表的集合不应触发 VectorStoreIndex 构造。"""
    mock_sc.from_defaults.return_value = MagicMock()

    node = MilvusIngestionNode(overwrite=True)
    ctx = {"settings": _make_settings(), "schema_docs": [], "val_docs": [], "row_docs": []}
    node.process(ctx)

    assert not mock_vs.called