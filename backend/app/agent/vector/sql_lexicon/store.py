# backend/app/agent/vector/sql_lexicon/store.py
import logging
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.vector_stores.milvus.utils import BM25BuiltInFunction

logger = logging.getLogger(__name__)

def get_milvus_vector_store(
    uri: str,
    collection_name: str,
    embed_dim: int,
    overwrite: bool = False,
    rrf_k: int = 60
) -> MilvusVectorStore:
    """
    统一封装创建和获取 Milvus 混合检索集合（含稀疏/密集检索、BM25分词、IP度量、RRF重排）。
    """
    logger.info(f"💾 正在连接/实例化 Milvus 集合: {collection_name} (overwrite={overwrite})")
    
    # 配置 BM25 中文分词（用于稀疏/全文检索）
    bm25_function = BM25BuiltInFunction(
        analyzer_params={
            "tokenizer": "jieba",
            "filter": ["cnalphanumonly"],
        },
    )
    
    return MilvusVectorStore(
        uri=uri,
        collection_name=collection_name,
        dim=embed_dim,
        enable_sparse=True,
        sparse_embedding_function=bm25_function,
        hybrid_ranker="RRFRanker",
        hybrid_ranker_params={"k": rrf_k},
        overwrite=overwrite,
        similarity_metric="IP",
    )
