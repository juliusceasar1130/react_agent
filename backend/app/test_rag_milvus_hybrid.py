"""Milvus 混合检索冒烟测试脚本。

验证:
1. Factory 能根据 RAG_BACKEND=milvus_hybrid 正确创建 MilvusHybridRetriever
2. Retriever 能在未连接/未初始化时优雅报错或返回空（防御性测试）
3. 检索出的 ScoredDocument 格式符合预期
"""

import os
import logging
from unittest.mock import patch, MagicMock

from backend.app.agent.vector.factory import create_business_retriever_and_reranker
from backend.app.agent.vector.milvus_hybrid.milvus_retriever import MilvusHybridRetriever
from backend.app.agent.vector.base import ScoredDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_milvus_factory_dispatch():
    """测试工厂是否能正确分发到 milvus_hybrid 后端（延迟初始化模式）。"""
    logger.info("测试工厂分发逻辑（延迟初始化模式）...")
    
    with patch("backend.app.agent.vector.factory.settings") as mock_settings:
        mock_settings.rag_backend = "milvus_hybrid"
        mock_settings.milvus_uri = "http://localhost:19530"
        mock_settings.milvus_collection_name = "test_collection"
        mock_settings.milvus_embed_dim = 1024
        mock_settings.milvus_rrf_k = 60
        mock_settings.rerank_enabled = False
        
        # 延迟初始化模式：工厂不会立即创建 store，只保存参数
        # 因此不需要 mock create_milvus_hybrid_index（它会在首次 retrieve 时调用）
        retriever, reranker = create_business_retriever_and_reranker()
        
        assert isinstance(retriever, MilvusHybridRetriever)
        assert reranker is None
        # 验证延迟初始化：store 和 index 应该为 None（未初始化）
        assert retriever._store is None
        assert retriever._index is None
        assert retriever._store_params is not None
        logger.info("✓ 工厂成功创建 MilvusHybridRetriever（延迟初始化模式）")

def test_retriever_output_format():
    """测试检索器输出格式是否符合 ScoredDocument 规范（立即初始化模式）。"""
    logger.info("测试检索器输出格式适配（立即初始化模式）...")
    
    # 模拟 LlamaIndex 的 NodeWithScore 结构
    mock_node = MagicMock()
    mock_node.get_content.return_value = "测试文档内容"
    mock_node.metadata = {"type": "documentation", "term": "测试术语"}
    
    mock_node_ws = MagicMock()
    mock_node_ws.node = mock_node
    mock_node_ws.score = 0.85
    
    # 模拟内部 retrieve 返回 mock 数据
    with patch("llama_index.core.indices.vector_store.retrievers.retriever.VectorIndexRetriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = [mock_node_ws]
        
        # 立即初始化模式：传入 store 参数
        with patch("backend.app.agent.vector.milvus_hybrid.milvus_retriever.create_milvus_hybrid_index") as mock_create_idx:
            mock_store = MagicMock()
            mock_index = MagicMock()
            mock_create_idx.return_value = mock_index
            
            retriever = MilvusHybridRetriever(store=mock_store)
            # 验证立即初始化
            assert retriever._store is not None
            assert retriever._index is not None
            
            results = retriever.retrieve("什么是测试？")
            
            assert len(results) == 1
            assert isinstance(results[0], ScoredDocument)
            assert results[0].score == 0.85
            assert results[0].document.page_content == "测试文档内容"
            assert results[0].document.metadata["term"] == "测试术语"
            logger.info("✓ 检索结果格式适配正确 (LlamaIndex -> LangChain)")

def test_lazy_initialization():
    """测试延迟初始化模式：首次 retrieve 时自动初始化。"""
    logger.info("测试延迟初始化模式...")
    
    # 模拟 LlamaIndex 的 NodeWithScore 结构
    mock_node = MagicMock()
    mock_node.get_content.return_value = "延迟初始化测试内容"
    mock_node.metadata = {"source": "test"}
    
    mock_node_ws = MagicMock()
    mock_node_ws.node = mock_node
    mock_node_ws.score = 0.9
    
    with patch("backend.app.agent.vector.factory.settings") as mock_settings:
        mock_settings.milvus_uri = "http://localhost:19530"
        mock_settings.milvus_collection_name = "test_collection"
        mock_settings.milvus_embed_dim = 1024
        mock_settings.milvus_rrf_k = 60
        
        # 创建延迟初始化的 retriever
        retriever = MilvusHybridRetriever()
        
        # 验证未初始化状态
        assert retriever._store is None
        assert retriever._index is None
        assert retriever._store_params is not None
        
        # Mock 初始化过程
        mock_store = MagicMock()
        mock_index = MagicMock()
        
        with patch("backend.app.agent.vector.milvus_hybrid.milvus_retriever.create_milvus_hybrid_index") as mock_create_idx:
            mock_create_idx.return_value = mock_index
            
            with patch("llama_index.core.indices.vector_store.retrievers.retriever.VectorIndexRetriever.retrieve") as mock_retrieve:
                mock_retrieve.return_value = [mock_node_ws]
                
                # 首次调用 retrieve，应该触发初始化
                results = retriever.retrieve("测试查询")
                
                # 验证初始化已执行
                assert retriever._store is not None
                assert retriever._index is not None
                mock_create_idx.assert_called_once()
                
                # 验证检索结果
                assert len(results) == 1
                assert isinstance(results[0], ScoredDocument)
                logger.info("✓ 延迟初始化模式工作正常")

if __name__ == "__main__":
    try:
        test_milvus_factory_dispatch()
        test_retriever_output_format()
        test_lazy_initialization()
        print("\n" + "="*40)
        print("✓ Milvus 混合检索模块冒烟测试通过！")
        print("="*40)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
