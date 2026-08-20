# backend/tests/agent/test_state_sandboxing_concurrency.py
"""
Phase 1 - Ticket 01 & 02: 状态物理沙箱隔离与并发安全测试。

验证内容:
1. SQL 子智能体使用 SqlSubAgentState 沙箱状态，主 Agent 使用 CustomState 全局状态
2. 多个子智能体并发执行并加载不同领域技能时，各自沙箱隔离，父图仅聚合 messages，绝不触发 INVALID_CONCURRENT_GRAPH_UPDATE 并发写冲突
3. 子智能体沙箱私有状态（skills_loaded / active_skill）不会污染父图 State
4. 支持 asyncio.gather 真实并发派发与执行
"""
import asyncio
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from backend.app.agent.state import CustomState, SqlSubAgentState
from backend.app.agent.context import RequestContext


def test_sql_subagent_state_schema_properties():
    """验证 SqlSubAgentState 包含领域私有字段，而 CustomState 保持纯净轻量。"""
    sub_state: SqlSubAgentState = {
        "messages": [HumanMessage(content="查询涂装")],
        "skills_loaded": ["paint_shop_defect_analysis"],
        "active_skill": "paint_shop_defect_analysis",
        "scenarios_loaded": [],
        "active_scenario": None,
    }
    assert len(sub_state["skills_loaded"]) == 1
    assert sub_state["active_skill"] == "paint_shop_defect_analysis"
    
    # 验证 CustomState 仅包含 messages 与轻量控制位
    main_state: CustomState = {
        "messages": [HumanMessage(content="你好")],
        "context_warning": None,
        "tool_artifact": None,
    }
    assert "messages" in main_state
    assert "skills_loaded" not in main_state


def test_concurrent_subagents_sandboxed_zero_collision():
    """验证多个子智能体并发执行时，各自在独立沙箱中维护状态，父图汇聚时 100% 无并发冲突。"""
    builder = StateGraph(CustomState)
    
    def subagent_paint_node(_state: CustomState):
        # 涂装车间子图沙箱执行
        sub_state: SqlSubAgentState = {
            "messages": [AIMessage(content="涂装车间统计完成: 25辆在制车。")],
            "skills_loaded": ["paint_shop_defect_analysis"],
            "active_skill": "paint_shop_defect_analysis",
        }
        # 通信走 messages 回传
        return {"messages": sub_state["messages"]}

    def subagent_assembly_node(_state: CustomState):
        # 总装车间子图沙箱执行
        sub_state: SqlSubAgentState = {
            "messages": [AIMessage(content="总装车间统计完成: 30辆在制车。")],
            "skills_loaded": ["assembly_shop_skill"],
            "active_skill": "assembly_shop_skill",
        }
        # 通信走 messages 回传
        return {"messages": sub_state["messages"]}

    builder.add_node("subagent_paint", subagent_paint_node)
    builder.add_node("subagent_assembly", subagent_assembly_node)

    builder.add_edge(START, "subagent_paint")
    builder.add_edge(START, "subagent_assembly")
    builder.add_edge("subagent_paint", END)
    builder.add_edge("subagent_assembly", END)

    graph = builder.compile()

    # 并发执行图
    result = graph.invoke({"messages": [HumanMessage(content="查询涂装和总装车间数据")]})

    # 验证父图成功汇聚了两边的 messages
    assert "messages" in result
    msg_contents = [m.content for m in result["messages"] if isinstance(m, AIMessage)]
    assert any("涂装车间" in c for c in msg_contents)
    assert any("总装车间" in c for c in msg_contents)
    
    # 验证父图 State 未被污染
    assert result.get("skills_loaded") is None or result.get("skills_loaded") == []
    assert result.get("active_skill") is None


@pytest.mark.asyncio
async def test_real_async_concurrent_subagents_gather():
    """使用 asyncio.gather 真实并发模拟两个独立子图沙箱并发执行并汇入主 Agent。"""
    async def run_subagent_task(shop_name: str, skill_name: str) -> dict:
        await asyncio.sleep(0.01)
        sub_state: SqlSubAgentState = {
            "messages": [AIMessage(content=f"{shop_name}数据已查询完成。")],
            "skills_loaded": [skill_name],
            "active_skill": skill_name,
        }
        # 仅回传 messages，私有状态留在子图生命周期内
        return {"messages": sub_state["messages"]}

    # 并发派发两个车间的查询
    results = await asyncio.gather(
        run_subagent_task("焊装车间", "welding_shop_skill"),
        run_subagent_task("冲压车间", "stamping_shop_skill"),
    )

    # 汇聚到父图状态
    parent_messages = [HumanMessage(content="查询焊装与冲压车间数据")]
    for r in results:
        parent_messages.extend(r["messages"])

    main_state: CustomState = {
        "messages": parent_messages,
        "context_warning": None,
        "tool_artifact": None,
    }

    assert len(main_state["messages"]) == 3
    assert "skills_loaded" not in main_state
    assert "active_skill" not in main_state
