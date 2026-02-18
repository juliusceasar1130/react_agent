"""
使用 langchain-postgres 创建向量集合的示例

参考文档: https://docs.langchain.com/oss/python/integrations/vectorstores/index

数据库地址: root:root@localhost:5432/agent_memory
"""

import asyncio
import platform
from typing import List
import os
import dotenv

dotenv.load_dotenv()  # 加载当前目录下的 .env 文件

from langchain_core.documents import Document
from langchain_postgres import PGEngine, PGVectorStore, PGVector
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# Windows 事件循环修复（psycopg3 需要 SelectorEventLoop）
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_vector_collection_method1():
    """
    方法1: 使用 PGVector 类创建向量集合（推荐，更简单）
    
    这是最简单的方式，直接使用 PGVector 类。
    目前推荐使用此方法，因为方法2（PGVectorStore）存在已知问题。
    """
    print("=" * 60)
    print("方法1: 使用 PGVector 创建向量集合（推荐）")
    print("=" * 60)
    
    # 数据库连接字符串
    # 注意：langchain-postgres 要求使用 postgresql+psycopg:// 格式
    connection_string = "postgresql+psycopg://root:root@localhost:5432/agent_memory"
    
    # 初始化 Embedding 模型
    # 需要设置 NVIDIA_API_KEY 环境变量
    embeddings = NVIDIAEmbeddings(
        model="baai/bge-m3",  # 或其他 NVIDIA embedding 模型
        api_key=os.environ["NVIDIA_API_KEY"]  # 免费层有调用限制
    )
    
    # 创建向量存储（会自动创建表）
    vector_store = PGVector(
        embeddings=embeddings,
        collection_name="my_docs",  # 集合名称，对应数据库表名
        connection=connection_string,
    )
    
    print(f"✓ 向量集合创建成功: collection_name='my_docs'")
    return vector_store


def create_vector_collection_method2():
    """
    方法2: 使用 PGEngine + PGVectorStore.create_sync 创建向量集合
    
    这种方式更底层，提供更多控制选项。
    
    ⚠️ 注意：此方法目前存在已知问题（Id column, langchain_id, does not exist），
    暂时无法正常使用。后续版本会修复此问题。
    当前推荐使用方法1（PGVector）。
    """
    print("=" * 60)
    print("方法2: 使用 PGEngine + PGVectorStore 创建向量集合（暂不可用）")
    print("=" * 60)
    
    # 数据库连接字符串
    connection_string = "postgresql+psycopg://root:root@localhost:5432/agent_memory"
    
    # 初始化 Embedding 模型
    embeddings = NVIDIAEmbeddings(
        model="baai/bge-m3",
    )
    
    # 创建 PGEngine
    pg_engine = PGEngine.from_connection_string(
        url=connection_string
    )
    
    # 创建向量存储（使用 table_name 而不是 collection_name）
    vector_store = PGVectorStore.create_sync(
        engine=pg_engine,
        table_name="test_table",  # 表名称
        embedding_service=embeddings,
    )
    
    print(f"✓ 向量集合创建成功: table_name='test_table'")
    return vector_store


def add_documents_example(vector_store):
    """
    添加文档到向量集合的示例
    """
    print("\n" + "=" * 60)
    print("添加文档到向量集合")
    print("=" * 60)
    
    # 创建示例文档
    documents = [
        Document(
            page_content="Python 是一种高级编程语言，广泛用于数据科学和机器学习。",
            metadata={"source": "python_intro", "category": "programming"}
        ),
        Document(
            page_content="LangChain 是一个用于构建 LLM 应用的框架。",
            metadata={"source": "langchain_intro", "category": "framework"}
        ),
        Document(
            page_content="PostgreSQL 是一个强大的开源关系型数据库。",
            metadata={"source": "postgres_intro", "category": "database"}
        ),
    ]
    
    # 添加文档到向量存储
    ids = vector_store.add_documents(documents)
    print(f"✓ 成功添加 {len(ids)} 个文档")
    print(f"  文档 IDs: {ids}")
    
    return ids


def search_documents_example(vector_store):
    """
    搜索文档的示例
    """
    print("\n" + "=" * 60)
    print("搜索文档")
    print("=" * 60)
    
    # 相似度搜索
    query = "什么是 Python？"
    results = vector_store.similarity_search(query, k=2)
    
    print(f"查询: '{query}'")
    print(f"找到 {len(results)} 个相关文档:")
    for i, doc in enumerate(results, 1):
        print(f"\n  {i}. {doc.page_content[:50]}...")
        print(f"     元数据: {doc.metadata}")
    
    # 带分数的相似度搜索
    print("\n" + "-" * 60)
    print("带分数的相似度搜索")
    print("-" * 60)
    
    results_with_scores = vector_store.similarity_search_with_score(query, k=2)
    print(f"查询: '{query}'")
    for i, (doc, score) in enumerate(results_with_scores, 1):
        print(f"\n  {i}. 相似度分数: {score:.4f}")
        print(f"     内容: {doc.page_content[:50]}...")
        print(f"     元数据: {doc.metadata}")


def filter_search_example(vector_store):
    """
    使用过滤器搜索文档的示例
    """
    print("\n" + "=" * 60)
    print("使用过滤器搜索文档")
    print("=" * 60)
    
    # 按元数据过滤搜索
    query = "编程语言"
    filter_dict = {"category": "programming"}
    
    results = vector_store.similarity_search(
        query,
        k=5,
        filter=filter_dict
    )
    
    print(f"查询: '{query}' (过滤条件: category='programming')")
    print(f"找到 {len(results)} 个相关文档:")
    for i, doc in enumerate(results, 1):
        print(f"\n  {i}. {doc.page_content[:50]}...")
        print(f"     元数据: {doc.metadata}")


def delete_documents_example(vector_store, document_ids: List[str]):
    """
    删除文档的示例
    """
    print("\n" + "=" * 60)
    print("删除文档")
    print("=" * 60)
    
    # 删除指定 ID 的文档
    if document_ids:
        success = vector_store.delete(ids=document_ids[:1])  # 删除第一个文档
        print(f"✓ 删除文档 ID: {document_ids[0]}, 结果: {success}")


def main():
    """
    主函数：演示完整的向量集合创建和使用流程
    """
    print("\n" + "=" * 60)
    print("langchain-postgres 向量集合创建示例")
    print("=" * 60)
    print("\n数据库地址: root:root@localhost:5432/agent_memory")
    print("请确保:")
    print("  1. PostgreSQL 数据库已启动")
    print("  2. 数据库 'agent_memory' 已创建")
    print("  3. 已安装 pgvector 扩展: CREATE EXTENSION IF NOT EXISTS vector;")
    print("  4. 已设置 NVIDIA_API_KEY 环境变量")
    print("\n")
    
    try:
        # 方法1: 使用 PGVector（推荐，当前可用）
        vector_store = create_vector_collection_method1()

        # 方法2: 使用 PGEngine + PGVectorStore（暂不可用，存在已知问题）
        # 问题：Id column, langchain_id, does not exist
        # 后续版本会修复，暂时注释掉
        # vector_store = create_vector_collection_method2()
        
        # 添加文档
        document_ids = add_documents_example(vector_store)
        
        # 搜索文档
        search_documents_example(vector_store)
        
        # 过滤搜索
        filter_search_example(vector_store)
        
        # 删除文档（可选）
        # delete_documents_example(vector_store, document_ids)
        
        print("\n" + "=" * 60)
        print("示例执行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n常见问题:")
        print("  1. 数据库连接失败 - 检查数据库是否运行，连接字符串是否正确")
        print("  2. pgvector 扩展未安装 - 在数据库中执行: CREATE EXTENSION IF NOT EXISTS vector;")
        print("  3. NVIDIA_API_KEY 未设置 - 设置环境变量或修改代码中的 API key")
        print("  4. Windows 事件循环错误 - 确保在代码开头设置了事件循环策略")
        raise


if __name__ == "__main__":
    main()
