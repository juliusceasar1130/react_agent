# milvus_init/__init__.py
"""
Milvus 数据库初始化与数据导入模块。

对外暴露:
  - init_milvus: 初始化 Milvus 混合检索索引的主函数
  - load_json_docs: 从目录加载 JSON 文档
  - split_nodes: 将文档切分为节点
  - init_hybrid_store: 构建 Milvus 混合检索索引
"""

# 使用相对导入，避免路径问题
# 注意：init_milvus 使用延迟导入，避免 python -m ...init_milvus 时产生 RuntimeWarning
from .data_loader import load_json_docs, split_nodes
from .init_store import init_hybrid_store


def __getattr__(name: str):
    """延迟导入 init_milvus，避免包加载时预加载同名模块导致 RuntimeWarning。"""
    if name == "init_milvus":
        from .init_milvus import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "init_milvus",
    "load_json_docs",
    "split_nodes",
    "init_hybrid_store",
]
