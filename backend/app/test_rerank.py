# backend/app/test_rerank.py
"""
NVIDIA Rerank 服务测试脚本

测试内容：
1. 降级测试：无效 API Key 时的降级行为
2. API 连通性测试：使用真实 API Key 测试
"""

import os
import sys
import logging

# 确保项目根路径在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from backend.app.agent.utils.rerank_service import NvidiaRerankService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_test_documents() -> list[Document]:
    """创建测试文档"""
    return [
        Document(
            page_content="L3F13 区域主要用于奥迪 A6L 和 A4L 的面漆喷涂，使用 PPG 水性漆。",
            metadata={"term": "L3F13", "type": "documentation", "domain": "paint_shop"},
        ),
        Document(
            page_content="Rollerbed 传输系统负责车身在各工位之间的传递，通过滚床驱动。",
            metadata={"term": "Rollerbed", "type": "documentation", "domain": "conveyor"},
        ),
        Document(
            page_content="ESTA (静电旋杯) 是涂装车间的核心喷涂设备，通过高速旋转雾化涂料。",
            metadata={"term": "ESTA", "type": "documentation", "domain": "paint_shop"},
        ),
        Document(
            page_content="VIN 码是车辆识别号码，17位字符，用于唯一标识每一辆汽车。",
            metadata={"term": "VIN", "type": "documentation", "domain": "general"},
        ),
        Document(
            page_content="PVC 密封胶工位在车身底部涂抹密封材料，起到防腐防水作用。",
            metadata={"term": "PVC", "type": "documentation", "domain": "paint_shop"},
        ),
    ]


def test_graceful_degradation():
    """测试 1: 降级测试 - 无效 API Key"""
    print("\n" + "=" * 60)
    print("测试 1: 降级测试 (无效 API Key)")
    print("=" * 60)

    service = NvidiaRerankService(
        api_key="invalid-key-for-testing",
        model="nvidia/rerank-qa-mistral-4b",
        top_n=3,
    )

    docs = create_test_documents()
    query = "L3F13有哪些奥迪车型？"

    result = service.rerank(query, docs)

    assert len(result) == len(docs), f"降级模式应返回所有文档，实际返回 {len(result)}"
    assert all(score == 0.0 for _, score in result), "降级模式分数应为 0.0"
    print("[PASS] 降级测试通过：API 失败后正确返回原始文档列表")


def test_empty_input():
    """测试 2: 空输入测试"""
    print("\n" + "=" * 60)
    print("测试 2: 空输入测试")
    print("=" * 60)

    service = NvidiaRerankService(
        api_key="test-key",
        model="nvidia/rerank-qa-mistral-4b",
        top_n=3,
    )

    # 空文档列表
    result = service.rerank("test query", [])
    assert result == [], "空文档应返回空列表"
    print("[PASS] 空文档列表测试通过")

    # 空查询
    result = service.rerank("", create_test_documents())
    assert len(result) == len(create_test_documents()), "空查询应返回所有文档"
    print("[PASS] 空查询测试通过")


def test_api_connectivity():
    """测试 3: API 连通性测试 (需要有效 API Key)"""
    print("\n" + "=" * 60)
    print("测试 3: API 连通性测试")
    print("=" * 60)

    api_key = os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        print("[SKIP] 未设置 NVIDIA_API_KEY，跳过连通性测试")
        return

    service = NvidiaRerankService(
        api_key=api_key,
        model="nvidia/rerank-qa-mistral-4b",
        top_n=3,
    )

    docs = create_test_documents()
    query = "L3F13有哪些奥迪车型？"

    result = service.rerank(query, docs)

    if result and any(score > 0 for _, score in result):
        print(f"[PASS] API 连通性测试通过! 返回 {len(result)} 条重排序结果:")
        for i, (doc, score) in enumerate(result):
            term = doc.metadata.get("term", "unknown")
            print(f"   #{i+1}: score={score:.4f}, term='{term}'")
    else:
        print("[WARN] API 返回了结果但分数为 0，可能是降级模式")


if __name__ == "__main__":
    print("=" * 60)
    print("NVIDIA Rerank 服务测试")
    print("=" * 60)

    test_graceful_degradation()
    test_empty_input()
    test_api_connectivity()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)
