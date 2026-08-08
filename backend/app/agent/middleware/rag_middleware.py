# backend/app/agent/middleware/rag_middleware.py
"""
业务知识 RAG 中间件

在用户消息时自动检索业务知识，并将检索结果作为系统消息注入到 messages 中。
支持可选的 Rerank 精排层（NVIDIA NIM）。
"""

import asyncio
import re
from typing import Any, List, Optional
import logging

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.runtime import Runtime

from backend.app.agent.state import CustomState
from backend.app.agent.utils import emit_stream_status
from backend.app.agent.vector.base import BaseRetriever, BaseReranker, ScoredDocument
from backend.app.agent.vector.sql_lexicon.retriever import DatabaseLexiconRetriever
from backend.app.config import settings

logger = logging.getLogger(__name__)


class BusinessRagMiddleware(AgentMiddleware[CustomState]):
    """
    业务知识 RAG 中间件

    - before_model: 在用户消息时检索业务知识，并将检索结果作为系统消息注入到 messages 中
    """

    state_schema = CustomState

    def __init__(
        self,
        retriever: BaseRetriever,
        doc_k: int = 5,
        score_threshold: Optional[float] = None,
        reranker: Optional[BaseReranker] = None,
        db: Optional[Any] = None,
    ) -> None:
        """
        Args:
            retriever: 业务知识检索器，实现 BaseRetriever 接口
            doc_k: Documentation 类型文档检索数量，默认 5
            score_threshold: 相似度分数阈值，只返回分数 >= threshold 的文档。
                            None 表示不过滤。注意：分数越高表示越相似
            reranker: 可选的精排服务实例，实现 BaseReranker 接口。
                      如果提供，将在向量检索后进行精排。API 失败时自动降级为纯向量排序。
            db: 可选的数据库连接实例，用于反射获取 DDL。
        """
        self.retriever = retriever
        self.doc_k = doc_k
        self.score_threshold = score_threshold
        self.reranker = reranker
        self.db = db
        # 用于标记业务知识系统消息的标识
        self._rag_system_message_id = "__business_rag_context__"
        
        # 异步加载数据库物理词典检索器，允许容灾降级
        self.lexicon_retriever = None
        if self.db is not None:
            try:
                self.lexicon_retriever = DatabaseLexiconRetriever()
                logger.info("BusinessRagMiddleware: DatabaseLexiconRetriever 初始化成功。")
            except Exception as e:
                logger.warning(f"BusinessRagMiddleware: DatabaseLexiconRetriever 初始化失败 (物理词典 RAG 降级): {e}")

    # --------- 工具方法 ---------

    @staticmethod
    def _is_human_message(msg: BaseMessage) -> bool:
        """判断是否为用户消息"""
        msg_type = getattr(msg, "type", None) or getattr(msg, "role", None)
        return msg_type == "human"

    def _extract_query(self, state: CustomState) -> tuple[List[BaseMessage], str] | None:
        """提取用户消息和查询文本，非用户消息或空查询时跳过。"""
        messages: List[BaseMessage] = state.get("messages", [])
        if not messages:
            return None
        last_msg = messages[-1]
        if not self._is_human_message(last_msg):
            return None
        user_query = getattr(last_msg, "content", None) or getattr(last_msg, "text", "")
        if not user_query:
            return None
        return messages, user_query

    @staticmethod
    def _format_knowledge_block(docs: List[Document]) -> str:
        """
        将检索结果格式化为系统提示词文本块
        仅格式化 Documentation 类型的文档

        Args:
            docs: Documentation 类型的文档列表

        Note:
            DDL 和 SQL Example 类型预留，后续开发
        """
        if not docs:
            return ""

        # 只格式化 Documentation 类型的文档
        parts: List[str] = []
        parts.append("## 1. 业务术语参考 (Business Terminology Reference)")

        for i, doc in enumerate(docs, start=1):
            meta = getattr(doc, "metadata", {}) or {}

            # 结合向量库设计文档中的字段：
            # - term: 业务术语
            # - aliases: 别名列表
            # - domain: 业务域
            term = meta.get("term")
            title = (
                term
                or meta.get("title")
                or meta.get("source")
                or f"业务术语 #{i}"
            )
            domain = meta.get("domain")
            aliases = meta.get("aliases") or []

            header_lines: List[str] = [f"#### {title}"]
            if domain:
                header_lines.append(f"- 业务域: {domain}")
            if isinstance(aliases, list) and aliases:
                # 仅展示前若干个别名，避免提示词过长
                alias_text = ", ".join(map(str, aliases[:5]))
                header_lines.append(f"- 别名: {alias_text}")

            header = "\n".join(header_lines)
            parts.append(f"{header}\n\n{doc.page_content}")

        return "\n\n".join(parts)

    def _has_rag_system_message(self, messages: List[BaseMessage]) -> bool:
        """检查 messages 中是否已包含业务知识系统消息"""
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # 检查是否有我们添加的业务知识标识
                content = getattr(msg, "content", "")
                if isinstance(content, str) and self._rag_system_message_id in content:
                    return True
                # 也检查 content_blocks 格式
                if hasattr(msg, "content_blocks"):
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if self._rag_system_message_id in block.get("text", ""):
                                return True
        return False

    # --------- 钩子实现 ---------

    def before_model(self, state: CustomState, runtime: Runtime) -> Optional[dict[str, Any]]:
        """
        在用户消息时检索业务知识，并将检索结果作为系统消息注入到 messages 中。(同步回退支持)
        """
        extracted = self._extract_query(state)
        if extracted is None:
            return None
        messages, user_query = extracted

        retrieved_docs: List[Document] = []
        lexicon_results = {"tables": [], "values": [], "rows": []}

        try:
            emit_stream_status(
                "正在检索业务知识与数据库词典 (同步)",
                stage="retrieving",
                source="business_rag",
            )
            scored_results: List[ScoredDocument] = self.retriever.retrieve(
                query=user_query,
                k=self.doc_k,
                score_threshold=self.score_threshold,
                doc_type="documentation",
            )
            retrieved_docs = [item.document for item in scored_results]

            if self.lexicon_retriever is not None:
                lexicon_results = self.lexicon_retriever.retrieve_all_sync(user_query)

        except Exception as e:
            logger.error(f"BusinessRagMiddleware 同步检索失败: {e}", exc_info=True)
            return None

        return self._format_and_assemble_state(user_query, messages, retrieved_docs, lexicon_results)

    async def abefore_model(self, state: CustomState, runtime: Runtime) -> Optional[dict[str, Any]]:
        """
        在用户消息时并发检索业务知识与数据库词典，并将检索结果作为系统消息注入到 messages 中。
        """
        extracted = self._extract_query(state)
        if extracted is None:
            return None
        messages, user_query = extracted

        retrieved_docs: List[Document] = []
        lexicon_results = {"tables": [], "values": [], "rows": []}

        try:
            emit_stream_status(
                "正在检索业务知识与数据库词典",
                stage="retrieving",
                source="business_rag",
            )

            tasks = [
                asyncio.to_thread(
                    self.retriever.retrieve,
                    query=user_query,
                    k=self.doc_k,
                    score_threshold=self.score_threshold,
                    doc_type="documentation",
                )
            ]
            if self.lexicon_retriever is not None:
                tasks.append(self.lexicon_retriever.retrieve_all(user_query))

            results = await asyncio.gather(*tasks)
            scored_results = results[0]
            retrieved_docs = [item.document for item in scored_results]

            if len(results) > 1:
                lexicon_results = results[1]

            # 记录检索结果和分数信息
            if scored_results:
                scores = [item.score for item in scored_results]
                logger.info(
                    "BusinessRagMiddleware: 检索到 %d 条 Documentation 类型业务文档 "
                    "(分数范围: %.4f - %.4f, 阈值: %s)",
                    len(retrieved_docs),
                    min(scores),
                    max(scores),
                    self.score_threshold if self.score_threshold is not None else "无",
                )
            else:
                logger.info(
                    "BusinessRagMiddleware: 未检索到符合条件的 Documentation 类型业务文档 (阈值: %s)",
                    self.score_threshold if self.score_threshold is not None else "无",
                )

            # Rerank 精排（如果启用，通过 to_thread 解绑事件循环阻塞）
            if self.reranker and retrieved_docs:
                try:
                    reranked_results: List[ScoredDocument] = await asyncio.to_thread(
                        self.reranker.rerank,
                        user_query,
                        retrieved_docs,
                    )
                    retrieved_docs = [item.document for item in reranked_results]
                    logger.info(
                        "BusinessRagMiddleware: Rerank 完成，精排后保留 %d 条文档",
                        len(retrieved_docs),
                    )
                except Exception as e:
                    logger.warning(
                        "BusinessRagMiddleware: Rerank 失败，降级使用原始向量检索结果: %s",
                        e,
                    )

        except Exception as e:
            logger.error(f"BusinessRagMiddleware 异步检索失败: {e}", exc_info=True)
            return None

        return self._format_and_assemble_state(user_query, messages, retrieved_docs, lexicon_results)

    def _format_and_assemble_state(
        self,
        user_query: str,
        messages: List[BaseMessage],
        retrieved_docs: List[Document],
        lexicon_results: dict
    ) -> Optional[dict[str, Any]]:
        # 1. 格式化业务术语说明 (Documentation)
        knowledge_block = self._format_knowledge_block(retrieved_docs)

        # 2. 三层词典并集处理与 DDL 装配
        ddl_block = ""
        mappings_block = ""
        table_lexicon_context = []
        structured_tables = []
        structured_values = []
        structured_rows = []

        if self.db is not None and getattr(self.db, "_custom_table_info", None) is not None:
            custom_table_info = self.db._custom_table_info
            
            # 1. 确定主表 (Primary Tables) - 独立决策，解决分数错配问题
            primary_tables = []
            seen_tables = set()
            schema_top_k = settings.lexicon_schema_top_k
            
            for node in lexicon_results.get("tables", []):
                t_name = node.node.metadata.get("table_name")
                if t_name:
                    key = t_name.lower()
                    if key not in seen_tables:
                        seen_tables.add(key)
                        primary_tables.append({
                            "table_name": t_name,
                            "summary": node.node.text
                        })
            primary_tables = primary_tables[:schema_top_k]
            primary_table_names = {t["table_name"].lower() for t in primary_tables}

            # 2. 跨层追加辅助表 (Auxiliary Tables) - 仅限值层且前 3 项内，最多追加 2 个，去除冗余和 spurious 过召回
            auxiliary_tables = []
            max_check_values = 3
            seen_aux = set()
            cross_layer_top_k = 2
            
            for node in lexicon_results.get("values", [])[:max_check_values]:
                t_name = node.node.metadata.get("table_name")
                if t_name:
                    key = t_name.lower()
                    if (key not in primary_table_names) and (key not in seen_aux):
                        seen_aux.add(key)
                        short_name = t_name.split(".")[-1]
                        display_text = (
                            custom_table_info.get(t_name)
                            or custom_table_info.get(short_name)
                            or f"表: {t_name}"
                        )
                        auxiliary_tables.append({
                            "table_name": t_name,
                            "ddl": display_text
                        })
                        if len(auxiliary_tables) >= cross_layer_top_k:
                            break

            # 3. 构造 DDL Block
            summary_parts = []
            for t in primary_tables:
                summary_parts.append(t["summary"])
                structured_tables.append({
                    "table_name": t["table_name"],
                    "ddl": t["summary"]
                })
                table_lexicon_context.append(t["table_name"])

            if summary_parts:
                ddl_block = "### 2.1 命中的主要数据库表结构 (Primary Table Schema)\n\n" + "\n\n---\n\n".join(summary_parts)

            # 辅助表 DDL 追加
            aux_parts = []
            for t in auxiliary_tables:
                aux_parts.append(t["ddl"])
                structured_tables.append({
                    "table_name": t["table_name"],
                    "ddl": t["ddl"]
                })
                table_lexicon_context.append(t["table_name"])

            if aux_parts:
                aux_block = (
                    "### 2.1.1 辅助参考的数据库表结构 (Auxiliary Table Schema)\n"
                    "(由于检索到相关列值条件，追加以下表结构供编写 SQL 过滤参考)\n\n"
                    + "\n\n---\n\n".join(aux_parts)
                )
                if ddl_block:
                    ddl_block = ddl_block + "\n\n" + aux_block
                else:
                    ddl_block = aux_block

            # 3. 格式化列值对照参考为 Markdown 表格（最多展示 lexicon_value_top_k 条）
            value_rows = []
            for node in lexicon_results.get("values", [])[:settings.lexicon_value_top_k]:
                meta = node.node.metadata
                t_name = meta.get('table_name', '')
                col_name = meta.get('column_name', '')
                exact_val = meta.get('exact_value', '')
                value_rows.append(f"| `{t_name}` | `{col_name}` | `'{exact_val}'` |")
                structured_values.append({
                    "table_name": t_name,
                    "column_name": col_name,
                    "exact_value": exact_val
                })

            value_block = ""
            if value_rows:
                value_block = (
                    "### 2.2 字段真实列值对照参考 (Fuzzy Value Alignment)\n\n"
                    "当用户输入的查询条件（如名称、类型等）不够规范或存在别名时，请参考下表映射进行条件过滤校准：\n\n"
                    "| 数据表 | 目标列名 | 真实物理字段值 (SQL Literal) |\n"
                    "| :--- | :--- | :--- |\n"
                    + "\n".join(value_rows)
                )

            # 4. 格式化实体主键与行属性关联参考（最多展示 lexicon_row_top_k 条）
            row_rows = []
            for node in lexicon_results.get("rows", [])[:settings.lexicon_row_top_k]:
                meta = node.node.metadata
                t_name = meta.get('table_name', '')
                pk_col = meta.get('primary_key_column', '')
                pk_val = meta.get('primary_key_val', '')
                row_content = meta.get('row_content', '')
                row_rows.append(f"| `{t_name}` | `{pk_col}` | `'{pk_val}'` | {row_content} |")
                structured_rows.append({
                    "table_name": t_name,
                    "primary_key_column": pk_col,
                    "primary_key_val": pk_val,
                    "row_content": row_content
                })

            row_block = ""
            if row_rows:
                row_block = (
                    "### 2.3 实体主键与行属性关联参考 (Entity Record Lookup)\n\n"
                    "以下是数据库中真实命中的实体主键及其相关核心属性，编写 SQL 时可供定位参考：\n\n"
                    "| 数据表 | 主键列 | 真实主键值 | 关联行核心属性描述 |\n"
                    "| :--- | :--- | :--- | :--- |\n"
                    + "\n".join(row_rows)
                )

        # 5. 合成系统消息内容
        rag_sections = []
        if knowledge_block:
            rag_sections.append(knowledge_block)
            
        db_sections = []
        if ddl_block:
            db_sections.append(ddl_block)
        if value_block:
            db_sections.append(value_block)
        if row_block:
            db_sections.append(row_block)
            
        if db_sections:
            db_block = "## 2. 数据库 Schema 与字段值映射对照 (Database Schema & Value Mapping)\n\n" + "\n\n".join(db_sections)
            rag_sections.append(db_block)

        if not rag_sections:
            logger.info("BusinessRagMiddleware: 未检索到任何相关辅助参考信息")
            return None

        rag_system_content = (
            f"{self._rag_system_message_id}\n\n"
            "# 混合检索辅助知识参考 (RAG & DB Lexicon)\n\n"
            "在回答问题或编写 SQL 时，请参考并结合下列辅助信息：\n\n"
            + "\n\n".join(rag_sections)
        )

        logger.info("BusinessRagMiddleware: 已将混合辅助知识注入到 state 的 lexicon_context")
        emit_stream_status(
            f"辅助知识与物理词典装配完毕 (DDL 并集共 {len(table_lexicon_context)} 张表)",
            stage="retrieving",
            source="business_rag",
        )

        return {
            "rag_context": retrieved_docs,
            "rag_query": user_query,
            "lexicon_context": {
                "formatted_text": rag_system_content,
                "tables": table_lexicon_context,
                "values_count": len(lexicon_results.get("values", [])),
                "rows_count": len(lexicon_results.get("rows", [])),
                "detail": {
                    "tables": structured_tables,
                    "values": structured_values,
                    "rows": structured_rows
                }
            }
        }
