"""
development/data_loader.py
==========================
数据加载与节点切分模块（初始化阶段使用）

职责：
  1. 从目录递归加载所有 JSON 文件 → LlamaIndex Document 列表
  2. 对 Document 列表进行语义切分 → Node 列表（供索引构建使用）

JSON 格式支持：
  - 列表格式：[{"document": "...", "metadata": {...}}, ...]
  - 单对象格式：{"document": "...", "metadata": {...}}
  - 兼容 "text" 字段作为 "document" 的别名

使用示例：
    from development.data_loader import load_json_docs, split_nodes

    docs = load_json_docs("./data/examples")
    nodes = split_nodes(docs, chunk_size=512, chunk_overlap=50)
"""

import os
import glob
import json
from typing import List

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode


def load_json_docs(data_dir: str) -> List[Document]:
    """
    从目录递归加载所有 JSON 文件，转为 LlamaIndex Document 对象列表。

    Args:
        data_dir: 包含 JSON 文件的目录路径（支持子目录递归）

    Returns:
        Document 列表；若目录下无 JSON 文件则返回空列表。
    """
    docs: List[Document] = []
    json_files = glob.glob(f"{data_dir}/**/*.json", recursive=True)

    if not json_files:
        print(f"  ⚠️  [data_loader] 在 {data_dir} 下未找到 JSON 文件")
        return docs

    for path in json_files:
        print(f"  📄 [data_loader] 加载文件: {os.path.basename(path)}")
        with open(path, encoding="utf-8") as f:
            items = json.load(f)

        if isinstance(items, dict):
            items = [items]

        for item in items:
            text = item.get("document", item.get("text", ""))
            metadata = item.get("metadata", {})
            if text.strip():
                docs.append(Document(text=text, metadata=metadata))

    print(f"  ✅ [data_loader] 共加载 {len(docs)} 个文档")
    return docs


def split_nodes(
    documents: List[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> List[BaseNode]:
    """
    对 Document 列表进行语义分块，返回 Node 列表。
    """
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nodes = splitter.get_nodes_from_documents(documents)
    print(f"  ✅ [data_loader] 共切分为 {len(nodes)} 个节点 "
          f"(chunk_size={chunk_size}, overlap={chunk_overlap})")
    return nodes
