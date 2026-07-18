# backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py
from unittest.mock import patch

from backend.app.agent.vector.sql_lexicon.pipeline.extractor_nodes import TableDDLExtractorNode


def test_table_ddl_extractor_uses_semantic_summary():
    """应嵌入语义摘要而非完整 DDL，且保留 table_name 元数据。"""
    fake_summaries = {
        "process_areas": "表: process_areas\n说明: 工艺区域\n字段: area_name(区域名)",
        "vehicle_body_types": "表: vehicle_body_types\n字段: body_type(车型)",
    }

    with patch(
        "backend.app.agent.vector.sql_lexicon.pipeline.extractor_nodes.fetch_table_semantic_summaries",
        return_value=fake_summaries,
    ):
        ctx = {
            "db_uri": "fake_uri",
            "engine_args": {},
            "lexicon_enabled_tables": {"ods.process_areas", "ods.vehicle_body_types"},
        }
        node = TableDDLExtractorNode()
        result = node.process(ctx)

    docs = result["schema_docs"]
    assert len(docs) == 2

    # 摘要文本不含 DDL 类型噪声
    for doc in docs:
        assert "CREATE TABLE" not in doc.text
        assert "VARCHAR" not in doc.text

    # table_name 元数据保留（rag_middleware 排序依赖）
    table_names = {doc.metadata["table_name"] for doc in docs}
    assert table_names == {"ods.process_areas", "ods.vehicle_body_types"}


def test_table_ddl_extractor_filters_non_whitelisted():
    """白名单外的表不应进入 schema_docs。"""
    fake_summaries = {
        "process_areas": "表: process_areas\n字段: area_name(区域名)",
        "sync_job_log": "表: sync_job_log\n字段: job_name",  # 不在白名单
    }

    with patch(
        "backend.app.agent.vector.sql_lexicon.pipeline.extractor_nodes.fetch_table_semantic_summaries",
        return_value=fake_summaries,
    ):
        ctx = {
            "db_uri": "fake_uri",
            "engine_args": {},
            "lexicon_enabled_tables": {"ods.process_areas"},
        }
        node = TableDDLExtractorNode()
        result = node.process(ctx)

    docs = result["schema_docs"]
    assert len(docs) == 1
    assert docs[0].metadata["table_name"] == "ods.process_areas"