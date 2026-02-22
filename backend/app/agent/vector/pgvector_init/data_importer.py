# backend/app/agent/vector/pgvector_init/data_importer.py
"""
数据导入核心逻辑

提供将数据导入到向量库的核心功能。
使用 langchain-postgres 的 PGVector 类实现。
"""

import asyncio
import platform
import logging
import os
import dotenv
from typing import List, Dict, Any, Optional, Callable
from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# Windows 事件循环修复（psycopg3 需要 SelectorEventLoop）
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

dotenv.load_dotenv()

logger = logging.getLogger(__name__)


def convert_to_documents(
    data: List[Dict[str, Any]],
    content_field: str = "document",
    metadata_fields: Optional[List[str]] = None,
) -> List[Document]:
    """
    将数据字典列表转换为 LangChain Document 列表

    支持两种格式：
    1. 扁平化格式：{"document": "...", "type": "...", "domain": "..."}
    2. 嵌套格式：{"document": "...", "metadata": {"type": "...", "domain": "..."}}

    Args:
        data: 数据字典列表
        content_field: 内容字段名，默认为 "document"
        metadata_fields: 元数据字段列表，如果为 None，则使用除 content_field 外的所有字段

    Returns:
        Document 列表
    """
    documents = []

    for item in data:
        if not isinstance(item, dict):
            logger.warning(f"跳过非字典类型的数据项: {type(item).__name__}")
            continue

        # 获取内容
        content = item.get(content_field, "")
        if not content:
            logger.warning(f"数据项缺少内容字段 '{content_field}'，跳过")
            continue

        # 获取元数据
        metadata = {}

        # 处理嵌套的 metadata 对象
        if "metadata" in item and isinstance(item["metadata"], dict):
            # 如果存在嵌套的 metadata 对象，将其扁平化
            nested_metadata = item["metadata"]
            for k, v in nested_metadata.items():
                if metadata_fields is None or k in metadata_fields:
                    # 如果值是基本类型，直接添加
                    if isinstance(v, (str, int, float, bool)):
                        metadata[k] = v
                    # 如果是列表，且列表元素都是基本类型，也添加
                    elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
                        metadata[k] = v
                    # 其他复杂类型尝试转换为字符串
                    elif v is not None:
                        try:
                            metadata[k] = str(v)
                        except Exception:
                            pass

        # 获取除 content_field 和 metadata 外的其他字段
        other_fields = {
            k: v for k, v in item.items()
            if k != content_field and k != "metadata"
        }

        # 如果指定了 metadata_fields，只使用这些字段
        if metadata_fields is not None:
            # 从扁平化的 other_fields 中筛选
            for k in metadata_fields:
                if k in other_fields:
                    v = other_fields[k]
                    if isinstance(v, (str, int, float, bool)):
                        metadata[k] = v
                    elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
                        metadata[k] = v
                    elif v is not None:
                        try:
                            metadata[k] = str(v)
                        except Exception:
                            pass
        else:
            # 使用除 content_field 和 metadata 外的所有字段
            for k, v in other_fields.items():
                if isinstance(v, (str, int, float, bool)):
                    metadata[k] = v
                elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v):
                    metadata[k] = v
                elif v is not None:
                    try:
                        metadata[k] = str(v)
                    except Exception:
                        pass

        doc = Document(page_content=content, metadata=metadata)
        documents.append(doc)

    return documents


def clear_vector_store_table(
    table_name: str,
    pg_connection_string: str,
) -> bool:
    """
    清空向量库集合中的所有数据

    PGVector 使用两个内部表存储数据：
    - langchain_pg_collection: 存储集合元数据
    - langchain_pg_embedding: 存储向量嵌入（通过 collection_id 关联）

    清空逻辑：
    1. 通过 collection_name 从 langchain_pg_collection 获取集合 UUID
    2. 删除 langchain_pg_embedding 中属于该集合的所有嵌入记录
    3. 删除 langchain_pg_collection 中的集合记录

    Args:
        table_name: 向量库集合名称（即 collection_name）
        pg_connection_string: PostgreSQL 连接字符串

    Returns:
        是否成功清空
    """
    try:
        from psycopg import connect, sql

        with connect(pg_connection_string) as conn:
            with conn.cursor() as cur:
                # 1. 获取集合的 UUID
                cur.execute(
                    sql.SQL("SELECT uuid FROM langchain_pg_collection WHERE name = %s"),
                    [table_name]
                )
                result = cur.fetchone()

                if result is None:
                    logger.warning(f"集合 '{table_name}' 不存在，跳过清空")
                    return True

                collection_uuid = result[0]
                logger.info(f"找到集合 '{table_name}' (UUID: {collection_uuid})")

                # 2. 删除属于该集合的所有嵌入记录
                cur.execute(
                    sql.SQL("DELETE FROM langchain_pg_embedding WHERE collection_id = %s"),
                    [collection_uuid]
                )
                deleted_embeddings = cur.rowcount
                logger.info(f"删除 {deleted_embeddings} 条嵌入记录")

                # 3. 删除集合记录
                cur.execute(
                    sql.SQL("DELETE FROM langchain_pg_collection WHERE uuid = %s"),
                    [collection_uuid]
                )
                conn.commit()

                logger.info(f"成功清空集合 '{table_name}' ({deleted_embeddings} 条记录)")
                return True

    except Exception as e:
        logger.error(f"清空集合失败: {e}")
        return False


def import_data_to_vector_store(
    data: List[Dict[str, Any]],
    table_name: str = "rag_store",
    pg_connection_string: Optional[str] = None,
    embedding_model: str = "baai/bge-m3",
    nvidia_api_key: Optional[str] = None,
    content_field: str = "document",
    metadata_fields: Optional[List[str]] = None,
    batch_size: int = 100,
    clear_existing: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    将数据导入到向量库

    Args:
        data: 要导入的数据列表
        table_name: 向量集合名称，默认为 "rag_store"
        pg_connection_string: PostgreSQL 连接字符串，如果为 None 则使用配置中的默认值
        embedding_model: Embedding 模型名称，默认为 "baai/bge-m3"
        nvidia_api_key: NVIDIA API Key，如果为 None 则从环境变量读取
        content_field: 内容字段名，默认为 "document"
        metadata_fields: 元数据字段列表，如果为 None，则使用除 content_field 外的所有字段
        batch_size: 批量导入大小，默认为 100
        clear_existing: 是否清空现有数据，默认为 False
        progress_callback: 进度回调函数，接收 (current, total) 参数

    Returns:
        成功导入的文档数量

    Raises:
        ValueError: 如果配置无效
        Exception: 如果导入过程中出现错误
    """
    if not data:
        logger.warning("数据列表为空，无需导入")
        return 0

    # 获取连接字符串
    if pg_connection_string is None:
        pg_connection_string = os.getenv("DATABASE_URL")
        if not pg_connection_string:
            raise ValueError(
                "未提供数据库连接字符串，请设置 DATABASE_URL 环境变量或传入 pg_connection_string 参数"
            )

    # 获取 NVIDIA API Key
    if nvidia_api_key is None:
        nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        if not nvidia_api_key:
            raise ValueError(
                "未提供 NVIDIA_API_KEY，请设置环境变量或传入 nvidia_api_key 参数"
            )

    logger.info(f"开始导入数据到向量库: table={table_name}, 数据量={len(data)}")

    # 清空现有数据（如果需要）
    if clear_existing:
        logger.warning(f"清空现有数据: table={table_name}")
        clear_vector_store_table(table_name, pg_connection_string)

    # 初始化 Embedding 模型
    logger.info(f"初始化 Embedding 模型: {embedding_model}")
    embeddings = NVIDIAEmbeddings(
        model=embedding_model,
        api_key=nvidia_api_key,
    )

    # 创建向量存储（使用 PGVector 类）
    logger.info(f"创建向量存储: collection_name={table_name}")
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name=table_name,
        connection=pg_connection_string,
    )

    # 转换为 Document 列表
    logger.info("正在转换数据格式...")
    documents = convert_to_documents(
        data=data,
        content_field=content_field,
        metadata_fields=metadata_fields,
    )

    if not documents:
        logger.warning("没有有效的文档可以导入")
        return 0

    logger.info(f"成功转换 {len(documents)} 个文档")

    # 批量导入
    total = len(documents)
    imported_count = 0

    try:
        for i in range(0, total, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(f"正在导入批次 {batch_num}/{total_batches} ({len(batch)} 个文档)...")

            # 添加文档到向量库
            ids = vector_store.add_documents(documents=batch)
            imported_count += len(ids)

            # 调用进度回调
            if progress_callback:
                progress_callback(imported_count, total)

            logger.info(f"批次 {batch_num} 导入完成，已导入 {imported_count}/{total} 个文档")

        logger.info(f"数据导入完成！共导入 {imported_count} 个文档")
        return imported_count

    except Exception as e:
        logger.error(f"导入过程中出现错误: {e}")
        raise
