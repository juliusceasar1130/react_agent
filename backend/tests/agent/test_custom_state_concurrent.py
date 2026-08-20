# backend/tests/agent/test_custom_state_concurrent.py
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from backend.app.agent.state import CustomState


def test_custom_state_concurrent_graph_update():
    """验证多个并行节点向 CustomState 写入时正常归约且不发生异常。"""
    builder = StateGraph(CustomState)

    def node_a(_state: CustomState):
        return {
            "messages": [AIMessage(content="响应 A")],
            "context_warning": True,
            "tool_artifact": {"kind": "chart_spec", "chart_id": "cht_aaa"},
        }

    def node_b(_state: CustomState):
        return {
            "messages": [AIMessage(content="响应 B")],
            "context_warning": False,
            "tool_artifact": {"kind": "file_export", "file_id": "exp_bbb"},
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
        "messages": [HumanMessage(content="初始问题")],
    })

    # 验证 messages 正常 append 且控制位正常被 Reducer 归约
    assert "messages" in result
    assert len(result["messages"]) == 3
    assert result["tool_artifact"] is not None
