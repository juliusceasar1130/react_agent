"""
简单的向量集合创建示例

最简化的示例，展示如何快速创建和使用向量集合。
"""

import asyncio
import platform
from langchain_core.documents import Document
from langchain_postgres import PGVector
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

# Windows 事件循环修复
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 1. 配置数据库连接
CONNECTION_STRING = "postgresql+psycopg://root:root@localhost:5432/agent_memory"
COLLECTION_NAME = "my_vector_collection"

# 2. 初始化 Embedding 模型
embeddings = NVIDIAEmbeddings(
    model="nvidia/nv-embedqa-e5-v5",  # 或其他模型
)

# 3. 创建向量存储
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
)

print(f"✓ 向量集合 '{COLLECTION_NAME}' 创建成功！")

# 4. 添加文档
documents = [
    Document(page_content="这是第一个文档", metadata={"id": 1}),
    Document(page_content="这是第二个文档", metadata={"id": 2}),
]

ids = vector_store.add_documents(documents)
print(f"✓ 添加了 {len(ids)} 个文档")

# 5. 搜索文档
results = vector_store.similarity_search("第一个", k=1)
print(f"✓ 搜索到 {len(results)} 个结果")
for doc in results:
    print(f"  内容: {doc.page_content}")
