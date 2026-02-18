# backend/app/agent/vector_init/__init__.py
"""
向量库数据导入模块

使用 langchain-postgres 的 PGVector 类实现从 JSON 文件导入数据到向量库的功能。
"""

from .json_loader import load_json_data
from .data_importer import (
    import_data_to_vector_store,
    clear_vector_store_table,
    convert_to_documents,
)

__all__ = [
    "load_json_data",
    "import_data_to_vector_store",
    "clear_vector_store_table",
    "convert_to_documents",
]
