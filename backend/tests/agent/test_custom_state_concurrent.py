# backend/tests/agent/test_custom_state_concurrent.py
from langchain_core.documents import Document
from langgraph.graph import StateGraph, START, END
from backend.app.agent.state import CustomState


def test_custom_state_concurrent_graph_update():
    """验证多个并行节点同时向 CustomState 的所有字段（包括 rag_context 和 rag_query）写入时不会发生并发更新冲突。"""
    builder = StateGraph(CustomState)

    def node_a(_state: CustomState):
        return {
            "rag_context": [Document(page_content="doc A")],
            "rag_query": "query A",
            "skills_loaded": ["skill_a"],
            "lexicon_context": {"term": "A"},
        }

    def node_b(_state: CustomState):
        return {
            "rag_context": [Document(page_content="doc B")],
            "rag_query": "query B",
            "skills_loaded": ["skill_b"],
            "lexicon_context": {"term": "B"},
        }

    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)

    builder.add_edge(START, "node_a")
    builder.add_edge(START, "node_b")
    builder.add_edge("node_a", END)
    builder.add_edge("node_b", END)

    graph = builder.compile()

    # 执行并发图：node_a 和 node_b 同时从 START 分发执行并在同一 Superstep 汇聚
    result = graph.invoke({
        "messages": [],
        "rag_context": [],
        "rag_query": "",
    })

    # 验证并发写入正常归约完成且无异常
    assert "rag_context" in result
    assert isinstance(result["rag_context"], list)
    assert len(result["rag_context"]) == 1
    assert result["rag_query"] in ("query A", "query B")
    assert result["skills_loaded"] in (["skill_a"], ["skill_b"])
