# backend/app/agent/context.py
"""
请求级瞬态上下文契约定义 (RequestContext)。

修改时间: 2026-08-16 Asia/Shanghai
主要修改内容:
- 基于 LangGraph / DeepAgent 原生 Context API 声明 RequestContext
- 承载单轮检索出的业务文档、物理词典 Schema (DDL) 及用户上下文
- Checkpointer 严格不持久化 Context，实现 0 字节存储膨胀
"""
from typing import Any, List, Optional, TypedDict
from langchain_core.documents import Document


class RequestContext(TypedDict, total=False):
    """
    单轮请求级瞬态上下文 (Transient Runtime Context)。
    通过 LangGraph context_schema 在运行时向所有中间件与工具透明向下透传。
    """
    lexicon_context: Optional[dict[str, Any]]
    rag_context: Optional[List[Document]]
    rag_query: Optional[str]
    user_id: Optional[str]
    session_id: Optional[str]
