# Schema 语义摘要嵌入优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `table_schema_store` 的嵌入内容从完整 DDL 改为语义摘要（表名+表注释+字段名及注释），并用 `from_nodes()` 跳过分块，提升表选择检索质量且不切断 DDL 语义。

**Architecture:** 当前架构中"嵌入文本"与"Agent 写 SQL 用的 DDL"已经解耦——嵌入文本（`node.text`）仅用于表选择（`rag_middleware.py` 仅读取 `node.metadata["table_name"]` 与 `node.score`），Agent 的完整 DDL 来自 `service.py` 独立调用 `fetch_table_definitions_with_comments` 生成的 `custom_table_info` 缓存。因此可在 `TableDDLExtractorNode` 中改嵌语义摘要而不影响 Agent。同时在 `MilvusIngestionNode` 用 `TextNode` + `VectorStoreIndex(nodes=nodes, ...)` 直接构造替代 `from_documents`，保证 1 文档 = 1 节点，杜绝分块。

**Tech Stack:** Python 3.12、SQLAlchemy（`inspect` 反射）、LlamaIndex（`VectorStoreIndex(nodes=...)` 直接构造跳过 chunking、`TextNode`）、Milvus、pytest（`unittest.mock`）。

## Global Constraints

- conda 环境：`py312_agent`；测试从项目根 `.tree/features/agent-llamaindex-rag` 运行。
- 遵循最小改动原则；不随意重构无关代码；保持现有风格。
- 不新增第三方依赖（`requirements.txt` 不变）。
- 单元测试用 `unittest.mock`，不依赖真实 DB/Milvus（对齐 `test_retriever.py` / `test_rag_middleware.py` 模式）。
- **未经用户允许不得执行 `git commit`。**
- `fetch_table_definitions_with_comments` 仍被 `service.py:216` 使用（供 Agent 的 `custom_table_info`），**不得删除或改变其行为**。

---

## File Structure

- **Modify** `backend/app/agent/utils/db_utils.py`
  - 新增 `_list_db_objects(inspector, include_views, include_materialized_views)`：从现有 `fetch_table_definitions_with_comments` 抽取的表/视图/物化视图列表逻辑（DRY）。
  - 新增 `_build_semantic_summary(conn, inspector, table, db_dialect)`：构建单表语义摘要（剥离类型/约束/样本）。
  - 新增 `fetch_table_semantic_summaries(db_uri, *, engine_args, include_views, include_materialized_views)`：返回 `{表名: 摘要}`。
  - 重构 `fetch_table_definitions_with_comments` 改用 `_list_db_objects`（纯抽取，行为不变）。

- **Modify** `backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py`
  - `TableDDLExtractorNode.process` 改调 `fetch_table_semantic_summaries`，用摘要作为 `Document.text`，保留 `metadata["table_name"]`。

- **Modify** `backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py`
  - `MilvusIngestionNode` 改用 `TextNode` + `VectorStoreIndex.from_nodes`；抽取 `_index_nodes` 辅助方法消除三段重复。

- **Create** `backend/tests/agent/utils/test_semantic_summary.py`：`_build_semantic_summary` 单元测试。
- **Create** `backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py`：`TableDDLExtractorNode` 单元测试。
- **Create** `backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py`：`MilvusIngestionNode` 单元测试。
- **Delete** `_debug_check_tables.py`（本会话产生的临时调试脚本）。
- **Modify** `changelog.md`：记录本次优化。

---

## Task 1: 在 db_utils.py 增加语义摘要提取能力

**Files:**
- Modify: `backend/app/agent/utils/db_utils.py`（在 `_process_single_table` 之后、`fetch_table_definitions_with_comments` 之前插入新函数；并重构 `fetch_table_definitions_with_comments` 的表列表逻辑）
- Test: `backend/tests/agent/utils/test_semantic_summary.py`（新建）

**Interfaces:**
- Produces:
  - `_list_db_objects(inspector, include_views: bool = False, include_materialized_views: bool = False) -> list[str]`
  - `_build_semantic_summary(conn, inspector, table: str, db_dialect: str) -> str | None`
  - `fetch_table_semantic_summaries(db_uri: str, *, engine_args: dict | None = None, include_views: bool = False, include_materialized_views: bool = False) -> Dict[str, str]`

- [ ] **Step 1: 写失败测试 `test_build_semantic_summary_with_column_comments`**

创建 `backend/tests/agent/utils/test_semantic_summary.py`：

```python
# backend/tests/agent/utils/test_semantic_summary.py
from unittest.mock import MagicMock

from backend.app.agent.utils.db_utils import _build_semantic_summary


def test_build_semantic_summary_with_column_comments():
    """字段注释来自 inspector 时，摘要含 字段名(注释) 且不含类型噪声。"""
    mock_conn = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": "涂装车间位置概览"}
    mock_inspector.get_columns.return_value = [
        {"name": "entity_type", "comment": "实体类型"},
        {"name": "entity_id", "comment": "实体ID"},
    ]

    result = _build_semantic_summary(
        mock_conn, mock_inspector, "mart_position_current_overview", "postgresql"
    )

    assert "表: mart_position_current_overview" in result
    assert "说明: 涂装车间位置概览" in result
    assert "entity_type(实体类型)" in result
    assert "entity_id(实体ID)" in result
    # 不含类型/约束噪声
    assert "VARCHAR" not in result
    assert "NOT NULL" not in result
    assert "BIGINT" not in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/utils/test_semantic_summary.py::test_build_semantic_summary_with_column_comments -v`
Expected: FAIL with `ImportError: cannot import name '_build_semantic_summary'`

- [ ] **Step 3: 在 db_utils.py 中新增三个函数**

在 `_process_single_table`（约 137-227 行）之后、`fetch_table_definitions_with_comments`（约 230 行）之前插入：

```python
def _list_db_objects(
    inspector, include_views: bool = False, include_materialized_views: bool = False
) -> list[str]:
    """列出数据库对象（表，可选视图/物化视图），去重保序。"""
    tables = inspector.get_table_names()
    if include_views:
        tables += inspector.get_view_names()
    if include_materialized_views:
        get_materialized_view_names = getattr(
            inspector, "get_materialized_view_names", None
        )
        if callable(get_materialized_view_names):
            tables += get_materialized_view_names()
    return list(dict.fromkeys(tables))


def _build_semantic_summary(
    conn, inspector, table: str, db_dialect: str
) -> str | None:
    """构建表的语义摘要（表名+表注释+字段名及注释），用于向量检索嵌入。

    与 _process_single_table 不同，本函数剥离类型/约束/样本等结构噪声，
    只保留对"表选择"有价值的语义信号。
    """
    try:
        table_comment_obj = inspector.get_table_comment(table)
        table_comment = (
            table_comment_obj.get("text", "") if table_comment_obj else ""
        )

        columns = inspector.get_columns(table)

        field_parts: list[str] = []
        for col in columns:
            col_name = col["name"]
            col_comment = col.get("comment")
            if not col_comment:
                if db_dialect == "postgresql":
                    col_comment = _get_column_comment_postgresql(conn, table, col_name)
                elif db_dialect == "mysql":
                    col_comment = _get_column_comment_mysql(conn, table, col_name)
            if col_comment:
                field_parts.append(f"{col_name}({col_comment})")
            else:
                field_parts.append(col_name)

        lines = [f"表: {table}"]
        if table_comment:
            lines.append(f"说明: {table_comment}")
        if field_parts:
            lines.append(f"字段: {', '.join(field_parts)}")
        return "\n".join(lines)

    except Exception as table_err:
        logger.error(f"构建表 {table} 语义摘要失败: {table_err}")
        return None


def fetch_table_semantic_summaries(
    db_uri: str,
    *,
    engine_args: dict | None = None,
    include_views: bool = False,
    include_materialized_views: bool = False,
) -> Dict[str, str]:
    """提取表的语义摘要字典 {表名: 摘要文本}，供 table_schema_store 嵌入使用。"""
    try:
        engine = create_engine(db_uri, **(engine_args or {}))
        inspector = inspect(engine)
        summaries: Dict[str, str] = {}

        db_dialect = engine.dialect.name
        logger.info(f"检测到数据库类型: {db_dialect}")

        tables = _list_db_objects(inspector, include_views, include_materialized_views)
        logger.info(f"找到 {len(tables)} 个数据库对象")

        with engine.connect() as conn:
            for table in tables:
                summary = _build_semantic_summary(conn, inspector, table, db_dialect)
                if summary:
                    summaries[table] = summary
                    logger.debug(f"已生成语义摘要: {table}")

        engine.dispose()
        logger.info(f"成功提取 {len(summaries)} 个表的语义摘要")
        return summaries

    except Exception as e:
        logger.error(f"提取表语义摘要失败: {e}")
        return {}
```

- [ ] **Step 4: 重构 `fetch_table_definitions_with_comments` 改用 `_list_db_objects`**

将 `fetch_table_definitions_with_comments` 内的表列表逻辑（约 259-272 行）：

```python
        # 获取所有表 / 视图 / 物化视图
        tables = inspector.get_table_names()
        if include_views:
            tables += inspector.get_view_names()
        if include_materialized_views:
            get_materialized_view_names = getattr(
                inspector,
                "get_materialized_view_names",
                None,
            )
            if callable(get_materialized_view_names):
                tables += get_materialized_view_names()
        tables = list(dict.fromkeys(tables))
        logger.info(f"找到 {len(tables)} 个数据库对象")
```

替换为：

```python
        # 获取所有表 / 视图 / 物化视图
        tables = _list_db_objects(inspector, include_views, include_materialized_views)
        logger.info(f"找到 {len(tables)} 个数据库对象")
```

- [ ] **Step 5: 运行测试确认通过**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/utils/test_semantic_summary.py::test_build_semantic_summary_with_column_comments -v`
Expected: PASS

- [ ] **Step 6: 补充其余 `_build_semantic_summary` 单元测试**

追加到 `backend/tests/agent/utils/test_semantic_summary.py`：

```python
def test_build_semantic_summary_no_table_comment():
    """无表注释时省略说明行，字段仍正常输出。"""
    mock_conn = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "area_name", "comment": "区域名"}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "process_areas", "postgresql")

    assert "表: process_areas" in result
    assert "说明:" not in result
    assert "area_name(区域名)" in result


def test_build_semantic_summary_fallback_column_comment():
    """inspector 未返回列注释时，走 PostgreSQL fallback 查询。"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = "回退注释"
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "col1", "comment": None}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "t1", "postgresql")

    assert "col1(回退注释)" in result


def test_build_semantic_summary_column_without_comment():
    """列无任何注释时，仅输出字段名（不带括号）。"""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = None
    mock_inspector = MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ""}
    mock_inspector.get_columns.return_value = [{"name": "col1", "comment": None}]

    result = _build_semantic_summary(mock_conn, mock_inspector, "t1", "postgresql")

    assert "字段: col1" in result
```

- [ ] **Step 7: 运行全部 Task 1 测试**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/utils/test_semantic_summary.py -v`
Expected: 4 passed

- [ ] **Step 8: 提交（待用户允许后执行）**

```bash
git add backend/app/agent/utils/db_utils.py backend/tests/agent/utils/test_semantic_summary.py
git commit -m "feat(db_utils): add semantic summary extraction for schema embedding"
```

---

## Task 2: TableDDLExtractorNode 改用语义摘要嵌入

**Files:**
- Modify: `backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py`（import 行约第 7 行；`TableDDLExtractorNode.process` 约 63-95 行）
- Test: `backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py`（新建）

**Interfaces:**
- Consumes: `fetch_table_semantic_summaries(db_uri, *, engine_args, include_views, include_materialized_views) -> Dict[str, str]`（Task 1 产出）
- Produces: `TableDDLExtractorNode.process` 输出的 `context["schema_docs"]` 中每个 `Document.text` 为语义摘要，`metadata["table_name"]` 保留全名。

- [ ] **Step 1: 写失败测试 `test_table_ddl_extractor_uses_semantic_summary`**

创建 `backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py::test_table_ddl_extractor_uses_semantic_summary -v`
Expected: FAIL with `AttributeError: ... module 'extractor_nodes' has no attribute 'fetch_table_semantic_summaries'`

- [ ] **Step 3: 修改 import**

将 `extractor_nodes.py` 第 7 行：

```python
from backend.app.agent.utils.db_utils import fetch_table_definitions_with_comments
```

改为：

```python
from backend.app.agent.utils.db_utils import fetch_table_semantic_summaries
```

- [ ] **Step 4: 修改 `TableDDLExtractorNode.process` 嵌入摘要**

将 `TableDDLExtractorNode.process` 内（约 72-89 行）：

```python
        custom_table_info = fetch_table_definitions_with_comments(
            db_uri, engine_args=engine_args, include_materialized_views=True
        )
        
        # 表级 DDL 同步源完全收拢为 lexicon_enabled_tables
        lexicon_enabled_short = {t.split(".")[-1].lower() for t in lexicon_enabled_tables}
        schema_docs = []
        
        for tbl_name, ddl in custom_table_info.items():
            tbl_name_lower = tbl_name.lower()
            if tbl_name_lower in lexicon_enabled_short:
                # 匹配并找回带模式名前缀的原表名格式，以便 metadata 存储一致性
                full_table_name = next(
                    (t for t in lexicon_enabled_tables if t.endswith(f".{tbl_name_lower}")),
                    tbl_name_lower
                )
                schema_docs.append(Document(
                    text=ddl,
                    metadata={"table_name": full_table_name, "description": f"表结构 {full_table_name}"}
                ))
```

替换为：

```python
        summaries = fetch_table_semantic_summaries(
            db_uri, engine_args=engine_args, include_materialized_views=True
        )

        # 表级语义摘要同步源完全收拢为 lexicon_enabled_tables
        lexicon_enabled_short = {t.split(".")[-1].lower() for t in lexicon_enabled_tables}
        schema_docs = []

        for tbl_name, summary in summaries.items():
            tbl_name_lower = tbl_name.lower()
            if tbl_name_lower in lexicon_enabled_short:
                # 匹配并找回带模式名前缀的原表名格式，以便 metadata 存储一致性
                full_table_name = next(
                    (t for t in lexicon_enabled_tables if t.endswith(f".{tbl_name_lower}")),
                    tbl_name_lower
                )
                schema_docs.append(Document(
                    text=summary,
                    metadata={"table_name": full_table_name, "description": f"表语义摘要 {full_table_name}"}
                ))
```

- [ ] **Step 5: 运行测试确认通过**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py::test_table_ddl_extractor_uses_semantic_summary -v`
Expected: PASS

- [ ] **Step 6: 补充白名单过滤测试**

追加到 `backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py`：

```python
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
```

- [ ] **Step 7: 运行全部 Task 2 测试**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py -v`
Expected: 2 passed

- [ ] **Step 8: 提交（待用户允许后执行）**

```bash
git add backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py
git commit -m "feat(sql_lexicon): embed semantic summary instead of full DDL in schema store"
```

---

## Task 3: MilvusIngestionNode 改用 from_nodes 跳过分块

**Files:**
- Modify: `backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py`（整文件 1-63 行重写为 helper + process）
- Test: `backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py`（新建）

**Interfaces:**
- Consumes: `context["schema_docs"]` / `val_docs` / `row_docs`（来自 Task 2 及既有 Column/Row 提取节点），每个为 LlamaIndex `Document`。
- Produces: 三个 Milvus 集合中每个 Document 对应 1 个 `TextNode`（1 文档 = 1 节点，不分块）。使用 `VectorStoreIndex(nodes=nodes, ...)` 直接构造，跳过 `from_documents` 的 `SentenceSplitter` 分块。

- [ ] **Step 1: 写失败测试 `test_ingestion_uses_from_nodes_without_chunking`**

创建 `backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py::test_ingestion_uses_from_nodes_without_chunking -v`
Expected: FAIL（当前实现调用 `from_documents`，`assert not mock_vs.from_documents.called` 失败）

- [ ] **Step 3: 重写 `milvus_load_node.py`**

将整个文件内容替换为：

```python
# backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py
import logging
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import TextNode
from backend.app.agent.vector.sql_lexicon.pipeline.base import PipelineNode
from backend.app.agent.vector.sql_lexicon.store import get_milvus_vector_store

logger = logging.getLogger(__name__)


class MilvusIngestionNode(PipelineNode):
    """加载节点：将提取生成的 Documents 存入 Milvus 集合。

    使用 TextNode + VectorStoreIndex.from_nodes 直接嵌入，跳过 SentenceSplitter
    分块，保证每个 Document 作为完整语义单元存入（1 文档 = 1 节点）。
    """

    def __init__(self, overwrite: bool = True):
        self.overwrite = overwrite

    def _index_nodes(self, settings, collection_name: str, docs: list) -> None:
        """将 Document 转为 TextNode（不分块）后嵌入到指定 Milvus 集合。"""
        if not docs:
            return
        store = get_milvus_vector_store(
            uri=settings.milvus_uri,
            collection_name=collection_name,
            embed_dim=settings.milvus_embed_dim,
            overwrite=self.overwrite,
            rrf_k=settings.milvus_rrf_k,
        )
        ctx = StorageContext.from_defaults(vector_store=store)
        nodes = [TextNode(text=d.text, metadata=d.metadata) for d in docs]
        VectorStoreIndex(nodes=nodes, storage_context=ctx)
        logger.info(f"✨ [Pipeline] {collection_name} 载入成功（{len(nodes)} 个节点，无分块）。")

    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在写入向量至 Milvus 集合...")
        settings = context["settings"]

        self._index_nodes(settings, "table_schema_store", context.get("schema_docs", []))
        self._index_nodes(settings, "db_value_lexicon", context.get("val_docs", []))
        self._index_nodes(settings, "db_row_lexicon", context.get("row_docs", []))

        return context
```

- [ ] **Step 4: 运行测试确认通过**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py::test_ingestion_uses_from_nodes_without_chunking -v`
Expected: PASS

- [ ] **Step 5: 补充空集合跳过测试**

追加到 `backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py`：

```python
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
```

- [ ] **Step 6: 运行全部 Task 3 测试**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py -v`
Expected: 2 passed

- [ ] **Step 7: 提交（待用户允许后执行）**

```bash
git add backend/app/agent/vector/sql_lexicon/pipeline/milvus_load_node.py backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py
git commit -m "refactor(sql_lexicon): use from_nodes to skip chunking in Milvus ingestion"
```

---

## Task 4: 端到端验证与清理

**Files:**
- Verify: `backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py`（集成测试，需 Milvus + Postgres + 嵌入服务在线）
- Verify: `backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py`（确认 Agent 仍取到完整 DDL）
- Delete: `_debug_check_tables.py`
- Modify: `changelog.md`

**Interfaces:**
- 无新接口；验证 Task 1-3 联动后系统行为正确。

**前置条件:** Milvus（`127.0.0.1:19530`）、PostgreSQL（`127.0.0.1:5432/analytics_db`）、嵌入服务（`127.0.0.1:8081`）均在线；`.env` 中 `MILVUS_OVERWRITE='true'`、`DB_LEXICON_SYNC_ON_STARTUP='true'`。

- [ ] **Step 1: 运行全部新增单元测试**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/utils/test_semantic_summary.py backend/tests/agent/vector/sql_lexicon/test_extractor_nodes.py backend/tests/agent/vector/sql_lexicon/test_milvus_load_node.py -v`
Expected: 全部 PASS（8 passed）

- [ ] **Step 2: 运行 rag_middleware 测试确认 Agent DDL 不受影响**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_rag_middleware.py -v`
Expected: PASS（该测试断言 `custom_table_info` 中的 `CREATE TABLE` 仍注入 Agent，验证 DDL 来源未变）

- [ ] **Step 3: 运行集成同步测试**

Run: `conda run -n py312_agent python -m pytest backend/tests/agent/vector/sql_lexicon/test_sync_metadata.py -v`
Expected: PASS，且日志输出 `table_schema_store 载入成功（N 个节点，无分块）`

- [ ] **Step 4: 验证 table_schema_store 节点数等于白名单表数（无分块）**

Run:
```bash
conda run -n py312_agent python -c "
from pymilvus import connections, Collection
from backend.app.config import settings
uri = settings.milvus_uri.replace('http://','').replace('https://','')
host, port = (uri.split(':') + ['19530'])[:2]
port = port.split('/')[0]
connections.connect('default', host=host, port=port)
col = Collection('table_schema_store'); col.flush()
print('table_schema_store entities:', col.num_entities)
connections.disconnect('default')
"
```
Expected: `table_schema_store entities:` 等于 `lexicon_enabled_tables` 白名单表数（当前 5），**不再是分块后的 7/13 等更大值**。

- [ ] **Step 5: 删除临时调试脚本**

Run: `rm -f _debug_check_tables.py`

- [ ] **Step 6: 更新 changelog.md**

在 changelog.md 顶部新增条目（保持现有格式）：

```markdown
- **三层词典 Schema 嵌入语义摘要优化**：`table_schema_store` 嵌入内容由完整 DDL 改为语义摘要（表名+表注释+字段名及注释），剥离 VARCHAR/BIGINT/NOT NULL 等结构噪声，提升表选择检索信噪比；`MilvusIngestionNode` 改用 `TextNode` + `VectorStoreIndex.from_nodes` 跳过 SentenceSplitter 分块，保证 1 表 = 1 节点。Agent 侧完整 DDL 仍由 `custom_table_info` 缓存提供，不受影响。
```

- [ ] **Step 7: 提交（待用户允许后执行）**

```bash
git add changelog.md
git rm -f _debug_check_tables.py 2>/dev/null || true
git commit -m "docs: record schema semantic summary embedding optimization"
```

---

## Self-Review

**1. Spec coverage:**
- 语义摘要嵌入（剥离类型/约束/样本）→ Task 1（`_build_semantic_summary`）+ Task 2（接入 `TableDDLExtractorNode`）。
- `from_nodes()` 不分块 → Task 3。
- 保留 `metadata["table_name"]`（rag_middleware 排序依赖）→ Task 2 测试显式断言。
- Agent 完整 DDL 不受影响 → Task 4 Step 2 通过 `test_rag_middleware.py` 验证（DDL 来自 `custom_table_info`，Task 1-3 均未触碰 `service.py`/`fetch_table_definitions_with_comments` 的输出语义）。
- 清理调试脚本 → Task 4 Step 5。
- changelog → Task 4 Step 6。

**2. Placeholder scan:** 无 TBD/TODO；每个代码步骤均含完整代码；测试步骤含可运行命令与预期输出。

**3. Type consistency:**
- `fetch_table_semantic_summaries` 签名在 Task 1 定义、Task 2 import 与 patch 路径一致。
- `_build_semantic_summary(conn, inspector, table, db_dialect)` 在 Task 1 定义与测试一致。
- `_index_nodes(settings, collection_name, docs)` 在 Task 3 定义与测试调用一致。
- `from_nodes` / `TextNode` 在 Task 3 生产代码与测试断言一致。
