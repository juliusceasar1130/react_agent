"""
Rerank 精排相关实现。

目前封装了 NVIDIA NIM Rerank 服务，后续可扩展为多模型/多厂商实现。
"""

from backend.app.agent.vector.rerank.nvidia_reranker import NvidiaReranker

__all__ = ["NvidiaReranker"]
