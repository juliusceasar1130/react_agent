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

from backend.app.agent.context import RequestContext
from backend.app.agent.state import CustomState
from backend.app.agent.utils import emit_stream_status
from backend.app.agent.vector.base import BaseRetriever, BaseReranker, ScoredDocument
from backend.app.agent.vector.sql_lexicon.retriever import DatabaseLexiconRetriever
from backend.app.config import settings

logger = logging.getLogger(__name__)


class BusinessRagMiddleware(AgentMiddleware[CustomState, RequestContext]):
    """
    业务知识 RAG 中间件

    - before_model: 在用户消息时检索业务知识，并将检索结果作为系统消息注入到 messages 中
    """

    state_schema = CustomState
    context_schema = RequestContext

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
        """判断是否为用户消息或 Task 输入消息"""
        msg_type = getattr(msg, "type", None) or getattr(msg, "role", None)
        return msg_type in ("human", "user")

    def _extract_query(self, state: CustomState, runtime: Optional[Runtime[RequestContext]] = None) -> tuple[List[BaseMessage], str] | None:
        """提取用户消息和查询文本，自适应主 Agent 原始 HumanMessage 与 SubAgent 包装的 Task 消息。"""
        messages: List[BaseMessage] = state.get("messages", [])
        if not messages:
            return None

        # 检查是否已包含业务知识系统消息标识，防止同一 Turn 内重复触发 RAG (Legacy 检查)
        if self._has_rag_system_message(messages):
            return None

        # 倒序查找最新的一条 Human/User 消息（主 Agent 匹配原始用户提问，SubAgent 匹配 Task 描述）
        user_query = None
        for msg in reversed(messages):
            if self._is_human_message(msg):
                content = getattr(msg, "content", None) or getattr(msg, "text", "")
                if isinstance(content, str) and content.strip():
                    user_query = content.strip()
                    break

        if not user_query:
            return None

        # 新架构防重复判定：若 runtime.context 中 rag_query 与当前 user_query 一致，证明当次 Turn 已做过 RAG 检索
        if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
            existing_rag_query = runtime.context.get("rag_query")
            if isinstance(existing_rag_query, str) and existing_rag_query == user_query:
                logger.debug("BusinessRagMiddleware: 当前 query 已在当次 Turn 中完成 RAG 检索，跳过重复检索。")
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

        knowledge_items = []
        for i, doc in enumerate(docs, 1):
            term = doc.metadata.get("term", f"术语_{i}")
            domain = doc.metadata.get("domain", "")
            domain_tag = f"【{domain}】" if domain else ""
            aliases = doc.metadata.get("aliases", [])
            alias_str = f"（别名：{'、'.join(aliases)}）" if aliases else ""

            item = f"{i}. {domain_tag}**{term}**{alias_str}\n   {doc.page_content}"
            knowledge_items.append(item)

        return (
            "## 1. 业务术语与定义说明 (Business Domain Knowledge)\n\n"
            + "\n\n".join(knowledge_items)
        )

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

    def before_model(self, state: CustomState, runtime: Runtime[RequestContext]) -> Optional[dict[str, Any]]:
        """
        在用户消息时同步检索业务知识与数据库词典，并将检索结果作为系统消息注入到 messages 中。
        """
        extracted = self._extract_query(state, runtime=runtime)
        if extracted is None:
            return None
        messages, user_query = extracted

        if self.retriever is None:
            logger.debug("BusinessRagMiddleware: retriever 为空，跳过知识检索")
            if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
                runtime.context["rag_context"] = []
                runtime.context["rag_query"] = user_query
                runtime.context["lexicon_context"] = None
                return None
            return None

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
            if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
                runtime.context["rag_context"] = []
                runtime.context["rag_query"] = user_query
                runtime.context["lexicon_context"] = None
                return None
            return None

        return self._format_and_assemble_state(
            user_query, messages, retrieved_docs, lexicon_results, runtime=runtime
        )

    async def abefore_model(self, state: CustomState, runtime: Runtime[RequestContext]) -> Optional[dict[str, Any]]:
        """
        在用户消息时并发检索业务知识与数据库词典，并将检索结果作为系统消息注入到 messages 中。
        """
        extracted = self._extract_query(state, runtime=runtime)
        if extracted is None:
            return None
        messages, user_query = extracted

        if self.retriever is None:
            logger.debug("BusinessRagMiddleware: retriever 为空，跳过知识检索")
            if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
                runtime.context["rag_context"] = []
                runtime.context["rag_query"] = user_query
                runtime.context["lexicon_context"] = None
                return None
            return None

        retrieved_docs: List[Document] = []
        lexicon_results = {"tables": [], "values": [], "rows": []}

        try:
            emit_stream_status(
                "正在检索业务知识与数据库词典 (并发)",
                stage="retrieving",
                source="business_rag",
            )
            if self.lexicon_retriever is not None:
                scored_results, lexicon_results = await asyncio.gather(
                    self.retriever.aretrieve(
                        query=user_query,
                        k=self.doc_k,
                        score_threshold=self.score_threshold,
                        doc_type="documentation",
                    ),
                    self.lexicon_retriever.retrieve_all(user_query),
                )
            else:
                scored_results = await self.retriever.aretrieve(
                    query=user_query,
                    k=self.doc_k,
                    score_threshold=self.score_threshold,
                    doc_type="documentation",
                )
            retrieved_docs = [item.document for item in scored_results]

            # Rerank 精排逻辑
            if self.reranker is not None and len(retrieved_docs) > 1:
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
            if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
                runtime.context["rag_context"] = []
                runtime.context["rag_query"] = user_query
                runtime.context["lexicon_context"] = None
                return None
            return None

        return self._format_and_assemble_state(user_query, messages, retrieved_docs, lexicon_results, runtime=runtime)

    def _format_and_assemble_state(
        self,
        user_query: str,
        messages: List[BaseMessage],
        retrieved_docs: List[Document],
        lexicon_results: dict,
        runtime: Optional[Runtime[RequestContext]] = None,
    ) -> Optional[dict[str, Any]]:
        # 1. 格式化业务术语说明 (Documentation)
        knowledge_block = self._format_knowledge_block(retrieved_docs)

        # 2. 三层词典并集处理与 DDL 装配
        ddl_block = ""
        value_block = ""
        row_block = ""
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
                        auxiliary_tables.append({
                            "table_name": t_name,
                            "summary": node.node.text
                        })
                        if len(auxiliary_tables) >= cross_layer_top_k:
                            break

            # 3. 规范化 DDL 注入与全量列注释提取
            all_resolved_tables = primary_tables + auxiliary_tables
            ddl_parts = []
            for t_info in all_resolved_tables:
                t_name = t_info["table_name"]
                t_ddl = custom_table_info.get(t_name)
                if t_ddl:
                    ddl_parts.append(t_ddl.strip())
                    table_lexicon_context.append({
                        "table_name": t_name,
                        "ddl": t_ddl.strip(),
                        "summary": t_info.get("summary", "")
                    })
                    structured_tables.append({
                        "table_name": t_name,
                        "ddl": t_ddl.strip(),
                        "summary": t_info.get("summary", "")
                    })

            if ddl_parts:
                ddl_block = (
                    "### 2.1 业务核心数据表结构定义 (Table DDL & Column Comments)\n\n"
                    "下列是与当前查询最相关的物理表 DDL 及注释，请在编写 SQL 时严格以此字段与关系为准：\n\n"
                    "```sql\n"
                    + "\n\n".join(ddl_parts)
                    + "\n```"
                )

            # 3. 格式化模糊值对照参考（最多展示 lexicon_value_top_k 条）
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
            if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
                runtime.context["lexicon_context"] = None
                runtime.context["rag_context"] = []
                runtime.context["rag_query"] = user_query
                return None
            return {
                "rag_context": [],
                "rag_query": user_query,
                "lexicon_context": None,
            }

        rag_system_content = (
            f"{self._rag_system_message_id}\n\n"
            "# 混合检索辅助知识参考 (RAG & DB Lexicon)\n\n"
            "在回答问题或编写 SQL 时，请参考并结合下列辅助信息：\n\n"
            + "\n\n".join(rag_sections)
        )

        lexicon_payload = {
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

        # 优先通过 Context API 写入运行时瞬态上下文 (0 字节入 Checkpoint)
        if runtime and getattr(runtime, "context", None) is not None and isinstance(runtime.context, dict):
            runtime.context["lexicon_context"] = lexicon_payload
            runtime.context["rag_context"] = retrieved_docs
            runtime.context["rag_query"] = user_query
            logger.info("BusinessRagMiddleware: 已将混合辅助知识注入到 RequestContext (0 Checkpoint 膨胀)")
            emit_stream_status(
                f"辅助知识与物理词典装配完毕 (DDL 并集共 {len(table_lexicon_context)} 张表)",
                stage="retrieving",
                source="business_rag",
            )
            return None

        logger.info("BusinessRagMiddleware: 已将混合辅助知识注入到 state 的 lexicon_context")
        emit_stream_status(
            f"辅助知识与物理词典装配完毕 (DDL 并集共 {len(table_lexicon_context)} 张表)",
            stage="retrieving",
            source="business_rag",
        )

        return {
            "rag_context": retrieved_docs,
            "rag_query": user_query,
            "lexicon_context": lexicon_payload,
        }
