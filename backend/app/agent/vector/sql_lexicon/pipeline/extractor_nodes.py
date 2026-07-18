# backend/app/agent/vector/sql_lexicon/pipeline/extractor_nodes.py
import logging
from sqlalchemy import create_engine, text
from llama_index.core import Document
from backend.app.agent.vector.sql_lexicon.pipeline.base import PipelineNode
from backend.app.skills.discovery import discover_domains
from backend.app.agent.utils.db_utils import fetch_table_semantic_summaries

logger = logging.getLogger(__name__)

class MetadataExtractorNode(PipelineNode):
    """提取器节点：扫描技能元数据，初始化白名单。"""
    
    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在扫描技能白名单元数据...")
        domains = discover_domains()
        
        lexicon_enabled_tables = set()
        columns_whitelist = {}
        rows_whitelist = {}
        
        for dom_name, domain_obj in domains.items():
            meta = domain_obj.meta
            
            # 允许进行三层向量存储嵌入同步的表白名单并集
            lexicon_enabled = {t.lower() for t in meta.get("lexicon_enabled_tables", [])}
            lexicon_enabled_tables.update(lexicon_enabled)
                
            for table, col_conf in meta.get("columns_lexicon_whitelist", {}).items():
                table_lower = table.lower()
                if table_lower in lexicon_enabled:
                    if isinstance(col_conf, list):
                        cols = [c.lower() for c in col_conf]
                        limit = 1000
                    elif isinstance(col_conf, dict):
                        cols = [c.lower() for c in col_conf.get("cols", [])]
                        limit = col_conf.get("limit", 1000)
                    else:
                        cols = []
                        limit = 1000
                        
                    if cols:
                        if table_lower not in columns_whitelist:
                            columns_whitelist[table_lower] = {"cols": set(), "limit": limit}
                        columns_whitelist[table_lower]["cols"].update(cols)
                        # 保留多技能合并下的最大配置 limit
                        columns_whitelist[table_lower]["limit"] = max(columns_whitelist[table_lower]["limit"], limit)
                    
            for table, row_conf in meta.get("rows_lexicon_whitelist", {}).items():
                table_lower = table.lower()
                if table_lower in lexicon_enabled:
                    rows_whitelist[table_lower] = {
                        "pk": row_conf["pk"].lower(),
                        "semantic_cols": [c.lower() for c in row_conf["semantic_cols"]],
                        "limit": row_conf.get("limit", 1000)
                    }
        
        context["lexicon_enabled_tables"] = lexicon_enabled_tables
        context["columns_whitelist"] = columns_whitelist
        context["rows_whitelist"] = rows_whitelist
        return context

class TableDDLExtractorNode(PipelineNode):
    """提取器节点：同步表级 DDL。"""
    
    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在从数据库提取表级 DDL...")
        db_uri = context["db_uri"]
        engine_args = context["engine_args"]
        lexicon_enabled_tables = context["lexicon_enabled_tables"]
        
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
                    text=summary.replace(f"表: {tbl_name}", f"表: {full_table_name}", 1),
                    metadata={"table_name": full_table_name, "description": f"表语义摘要 {full_table_name}"}
                ))
                
        context["schema_docs"] = schema_docs
        logger.info(f"📊 [Pipeline] 表 DDL 提取完成，共 {len(schema_docs)} 张表。")
        return context

class ColumnLexiconExtractorNode(PipelineNode):
    """提取器节点：同步去重列值字典。"""
    
    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在从数据库提取列值字典...")
        db_uri = context["db_uri"]
        columns_whitelist = context["columns_whitelist"]
        engine_args = context["engine_args"]
        
        engine = create_engine(db_uri, **engine_args)
        val_docs = []
        
        with engine.connect() as conn:
            for table, conf in columns_whitelist.items():
                cols = conf["cols"]
                limit = conf["limit"]
                for col_name in cols:
                    val_query = f"SELECT DISTINCT {col_name} FROM {table} WHERE {col_name} IS NOT NULL LIMIT {limit}"
                    results = conn.execute(text(val_query)).fetchall()
                    for r in results:
                        val = str(r[0]).strip()
                        if val:
                            val_docs.append(Document(
                                text=f"表: {table}, 列: {col_name}, 列值: {val}",
                                metadata={"table_name": table, "column_name": col_name, "exact_value": val, "semantic_alias": val}
                            ))
                            
        context["val_docs"] = val_docs
        logger.info(f"📊 [Pipeline] 去重列值提取完成，共 {len(val_docs)} 个。")
        return context

class RowLexiconExtractorNode(PipelineNode):
    """提取器节点：同步行级实体数据。"""
    
    def process(self, context: dict) -> dict:
        logger.info("🔌 [Pipeline] 正在从数据库提取行实体数据...")
        db_uri = context["db_uri"]
        rows_whitelist = context["rows_whitelist"]
        engine_args = context["engine_args"]
        
        engine = create_engine(db_uri, **engine_args)
        row_docs = []
        
        with engine.connect() as conn:
            for table, conf in rows_whitelist.items():
                pk = conf["pk"]
                semantic_cols = conf["semantic_cols"]
                limit = conf["limit"]
                
                all_cols = [pk] + semantic_cols
                query = f"SELECT {', '.join(all_cols)} FROM {table} LIMIT {limit}"
                results = conn.execute(text(query)).fetchall()
                
                for r in results:
                    r_dict = dict(zip(all_cols, r))
                    pk_val = str(r_dict[pk])
                    row_text_parts = [f"{col}={r_dict[col]}" for col in semantic_cols if r_dict[col] is not None]
                    row_content = ", ".join(row_text_parts)
                    if row_content:
                        row_docs.append(Document(
                            text=row_content,
                            metadata={"table_name": table, "primary_key_column": pk, "primary_key_val": pk_val, "row_content": row_content}
                        ))
                        
        context["row_docs"] = row_docs
        logger.info(f"📊 [Pipeline] 行级实体提取完成，共 {len(row_docs)} 个。")
        return context
