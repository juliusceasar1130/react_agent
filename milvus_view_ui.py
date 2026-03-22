
from pymilvus import MilvusClient, MilvusException
import time

try:
    print("🔌 连接 Milvus...")
    
    max_retries = 5
    retry_delay = 2
    client = None
    
    for attempt in range(max_retries):
        try:
            client = MilvusClient(uri="http://localhost:19530", timeout=5)
            # Try a simple operation to check readiness
            client.list_collections()
            print("✅ Milvus 连接成功！")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️  连接尝试 {attempt + 1}/{max_retries} 失败: {e}")
                print(f"⏳ 等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                raise e

    # 1. 查看所有 Collection
    collections = client.list_collections()
    print(f"\n📂 当前 Collection 列表: {collections}")

    if not collections:
        print("⚠️ 未发现任何 Collection，可能是还没有运行主程序 `llamaindex_rag_compare.py`。")
        exit()

    target_collections = ["rag_store"]

    for coll_name in target_collections:
        if coll_name in collections:
            print(f"\n" + "="*50)
            print(f"🔍 查看 Collection: [{coll_name}]")
            
            # 2. 获取 Schema 确认字段名
            desc = client.describe_collection(coll_name)
            all_fields = [f['name'] for f in desc['fields']]
            print(f"📊 字段列表: {all_fields}")
            
            # 3. 统计数据量
            stats = client.get_collection_stats(coll_name)
            print(f"📈 统计信息: {stats}")

            # 4. 查询数据，包含向量字段预览
            print("\n📝 数据预览:")
            results = client.query(
                collection_name=coll_name,
                filter="",
                limit=1,
                output_fields=["text", "embedding"]  # sparse_embedding 不支持直接读取 raw data
            )
            
            if not results:
                print("  (无数据)")
                continue

            for i, r in enumerate(results, 1):
                text_preview = r.get('text', '').replace('\n', ' ')[:80]
                print(f"  [文本内容]: {text_preview}...")
                
                # 稠密向量信息
                if 'embedding' in r:
                    vec = r['embedding']
                    print(f"  [稠密向量 (Dense)]: 维度 {len(vec)}, 示例: {vec[:3]}...")
                
                # 稀疏向量 (BM25) 信息
                if 'sparse_embedding' in r:
                    s_vec = r['sparse_embedding']
                    # 稀疏向量在 PyMilvus 中返回格式通常为字典 {index: value}
                    print(f"  [稀疏向量 (Sparse/BM25)]: 活跃词项数 {len(s_vec)}, 示例: {dict(list(s_vec.items())[:3])}...")
        else:
            print(f"\n⚠️  Collection [{coll_name}] 尚未创建。")

except Exception as e:
    print(f"\n❌ 连接或查询失败: {e}")
    print("请检查 Docker 容器是否正常运行 (docker ps)")
