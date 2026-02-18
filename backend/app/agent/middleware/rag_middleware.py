# backend/app/agent/middleware/rag_middleware.py
"""
业务知识 RAG 中间件

在用户消息时自动检索业务知识，并将检索结果作为系统消息注入到 messages 中。
支持可选的 Rerank 精排层（NVIDIA NIM）。
"""

from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.agent.utils.pgvector_wrapper import PgVectorStoreWrapper
    from backend.app.agent.utils.rerank_service import NvidiaRerankService
import logging

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.documents import Document
from langgraph.runtime import Runtime

from backend.app.agent.state import CustomState

logger = logging.getLogger(__name__)


class BusinessRagMiddleware(AgentMiddleware[CustomState]):
    """
    业务知识 RAG 中间件

    - before_model: 在用户消息时检索业务知识，并将检索结果作为系统消息注入到 messages 中
    """

    state_schema = CustomState

    def __init__(
        self,
        vector_store: "PgVectorStoreWrapper",
        doc_k: int = 5,
        score_threshold: Optional[float] = None,
        rerank_service: Optional["NvidiaRerankService"] = None,
    ) -> None:
        """
        Args:
            vector_store: PgVectorStoreWrapper 实例（基于官方 PGVector 的轻量包装）
            doc_k: Documentation 类型文档检索数量，默认 5
            score_threshold: 相似度分数阈值，只返回分数 >= threshold 的文档。
                            None 表示不过滤。注意：分数越高表示越相似
            rerank_service: 可选的 Rerank 服务实例。如果提供，将在向量检索后
                          进行精排。API 失败时自动降级为纯向量排序。
        """
        self.vector_store = vector_store
        self.doc_k = doc_k
        self.score_threshold = score_threshold
        self.rerank_service = rerank_service
        # 用于标记业务知识系统消息的标识
        self._rag_system_message_id = "__business_rag_context__"

    # --------- 工具方法 ---------

    @staticmethod
    def _is_human_message(msg: BaseMessage) -> bool:
        """判断是否为用户消息"""
        msg_type = getattr(msg, "type", None) or getattr(msg, "role", None)
        return msg_type == "human"

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
        parts.append("### 业务术语说明 (Documentation)")

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
        在用户消息时检索业务知识，并将检索结果作为系统消息注入到 messages 中。
        """
        messages: List[BaseMessage] = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]

        # 只在用户消息时执行检索
        if not self._is_human_message(last_msg):
            logger.info("BusinessRagMiddleware.before_model: 非用户消息，跳过检索")
            return None

        user_query = getattr(last_msg, "content", None) or getattr(last_msg, "text", "")
        if not user_query:
            return None

        # 只检索 Documentation 类型的业务知识
        retrieved_docs: List[Document] = []

        try:
            # 使用带分数的检索方法，并根据阈值过滤
            results_with_scores = self.vector_store.similarity_search_by_type_with_score(
                query=user_query,
                doc_type="documentation",
                k=self.doc_k,
                score_threshold=self.score_threshold,
            )
            
            # 提取文档列表
            retrieved_docs = [doc for doc, score in results_with_scores]
            
            # 记录检索结果和分数信息
            if results_with_scores:
                scores = [score for _, score in results_with_scores]
                logger.info(
                    f"BusinessRagMiddleware: 检索到 {len(retrieved_docs)} 条 Documentation 类型业务文档 "
                    f"(分数范围: {min(scores):.4f} - {max(scores):.4f}, "
                    f"阈值: {self.score_threshold if self.score_threshold is not None else '无'})"
                )
            else:
                logger.info(
                    f"BusinessRagMiddleware: 未检索到符合条件的 Documentation 类型业务文档 "
                    f"(阈值: {self.score_threshold if self.score_threshold is not None else '无'})"
                )

            # ---- Rerank 精排（如果启用） ----
            if self.rerank_service and retrieved_docs:
                try:
                    reranked = self.rerank_service.rerank(user_query, retrieved_docs)
                    retrieved_docs = [doc for doc, score in reranked]
                    logger.info(
                        f"BusinessRagMiddleware: Rerank 完成，精排后保留 {len(retrieved_docs)} 条文档"
                    )
                except Exception as e:
                    logger.warning(
                        f"BusinessRagMiddleware: Rerank 失败，降级使用原始向量检索结果: {e}"
                    )

        except Exception as e:
            logger.error(f"BusinessRagMiddleware: 向量检索失败: {e}", exc_info=True)
            return None

        # 格式化检索结果为系统提示词
        knowledge_block = self._format_knowledge_block(retrieved_docs)
        if not knowledge_block:
            logger.info("BusinessRagMiddleware: 未检索到相关业务知识")
            return None

        # 构建业务知识系统消息内容
        rag_system_content = (
            f"{self._rag_system_message_id}\n\n"
            "## 业务知识库\n\n"
            "下面是与当前用户问题相关的业务资料，请在回答中充分利用这些信息：\n\n"
            f"{knowledge_block}\n"
        )

        # 创建系统消息
        rag_system_message = SystemMessage(content=rag_system_content)

        # 检查是否已经存在业务知识系统消息，如果存在则替换，否则添加到开头
        new_messages = []
        rag_message_added = False

        for msg in messages:
            if isinstance(msg, SystemMessage):
                content = getattr(msg, "content", "")
                # 如果找到已有的业务知识系统消息，替换它
                if isinstance(content, str) and self._rag_system_message_id in content:
                    if not rag_message_added:
                        new_messages.append(rag_system_message)
                        rag_message_added = True
                    # 跳过旧的消息
                    continue
                # 检查 content_blocks 格式
                elif hasattr(msg, "content_blocks"):
                    should_replace = False
                    for block in msg.content_blocks:
                        if isinstance(block, dict) and block.get("type") == "text":
                            if self._rag_system_message_id in block.get("text", ""):
                                should_replace = True
                                break
                    if should_replace:
                        if not rag_message_added:
                            new_messages.append(rag_system_message)
                            rag_message_added = True
                        continue

            new_messages.append(msg)

        # 如果没有找到已有的业务知识系统消息，则在开头添加
        if not rag_message_added:
            new_messages.insert(0, rag_system_message)

        logger.info("BusinessRagMiddleware: 已将业务知识注入到 messages 作为系统消息")
        logger.info(
            f"BusinessRagMiddleware: 更新后的 messages 包含 {len(new_messages)} 条消息 "
            f"(注意: 初始化时的 system_prompt 不在 state['messages'] 中，"
            f"而是通过 ModelRequest.system_message 传递，因此这里看不到)"
        )
        logger.debug(f"BusinessRagMiddleware: messages 详情: {new_messages}")

        # 返回更新后的 state
        return {
            "messages": new_messages,
            "rag_context": retrieved_docs,
            "rag_query": user_query,
        }
