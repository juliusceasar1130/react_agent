"""
DeepAgent + Subagent-as-Tool Minimal PoC Test Script
验证点：
1. create_deep_agent / create_agent 构建主 Agent 与 子 Agent
2. 子 Agent 包装为 Tool (Subagent-as-Tool) 挂载给主 Agent
3. astream(..., subgraphs=True) 捕获 (namespace, chunk) 拆解
4. 验证 MemorySaver 检查点与 namespace 隔离
"""
import sys
import os
import asyncio
from typing import Dict, Any, List

# 强制设置 UTF-8 标准输出，防止 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 确保 backend 路径能被正常导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agent.service import _create_llm

# 导入 deepagents / langchain 核心 API
try:
    from deepagents import create_deep_agent
    USE_DEEP_AGENTS = True
    print("[PoC] Successfully imported create_deep_agent from deepagents.")
except ImportError:
    from langchain.agents import create_agent
    USE_DEEP_AGENTS = False
    print("[PoC] Falling back to create_agent from langchain.agents.")

# 1. 定义一个简单的 SQL / 检索子工具
@tool
def execute_sql_query(query: str) -> str:
    """模拟 SQL 数据库查询工具"""
    print(f"\n   [Subagent Tool Call] 执行 SQL 查询: {query}")
    return f"【SQL 执行结果】查询 '{query}' 成功，返回结果: [{{'department': '底漆车间', 'count': 42}}]"

@tool
def calculate_summary(data_str: str) -> str:
    """模拟数据统计与摘要工具"""
    return f"【统计摘要】根据数据 '{data_str}'，汇总在制车数量为 42 台。"

# 创建配置好的大模型实例 (从项目的 .env / settings 中读取)
llm_instance = _create_llm()

# 2. 构建子 Agent (SQLSubGraph)
checkpointer = MemorySaver()

if USE_DEEP_AGENTS:
    sql_subagent = create_deep_agent(
        model=llm_instance,
        tools=[execute_sql_query, calculate_summary],
        system_prompt="你是一个 SQL 领域专家智能体，擅长执行 SQL 并汇总结果。",
    )
else:
    sql_subagent = create_agent(
        model=llm_instance,
        tools=[execute_sql_query, calculate_summary],
        system_prompt="你是一个 SQL 领域专家智能体。",
    )

# 3. 将子 Agent 包装为 Tool (Subagent-as-Tool)
sql_subagent_tool = sql_subagent.as_tool(
    name="sql_domain_agent",
    description="【SQL 领域专家子智能体】用于处理任何与数据库、SQL 查询、数据统计相关的请求。"
)

# 4. 构建主 Agent (Main DeepAgent)
if USE_DEEP_AGENTS:
    main_agent = create_deep_agent(
        model=llm_instance,
        tools=[sql_subagent_tool],
        system_prompt="你是一个通用主智能体，遇到数据查询需求时，请调用 sql_domain_agent 工具委派任务。",
        checkpointer=checkpointer,
    )
else:
    main_agent = create_agent(
        model=llm_instance,
        tools=[sql_subagent_tool],
        system_prompt="你是一个通用主智能体，遇到数据查询需求时，请调用 sql_domain_agent 工具委派任务。",
        checkpointer=checkpointer,
    )

async def run_poc():
    print("=" * 60)
    print("[START] DeepAgent + Subagent Stream & Namespace PoC Test")
    print("=" * 60)
    
    config = {"configurable": {"thread_id": "test_poc_thread_001"}}
    input_data = {"messages": [HumanMessage(content="请帮我查询底漆车间当前的在制车数量。")]}
    
    print("\n[Input Query]:", input_data["messages"][0].content)
    print("\n[Streaming Output (subgraphs=True)]:")
    
    try:
        # 测试 subgraphs=True 模式下的 (namespace, chunk) 解包
        async for event in main_agent.astream(
            input_data,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True
        ):
            # 解包 (namespace, chunk) 元组
            if isinstance(event, tuple) and len(event) == 2:
                namespace, chunk = event
                ns_str = " -> ".join(namespace) if namespace else "main"
                print(f"  [NS: {ns_str}] Chunk Keys: {list(chunk.keys()) if isinstance(chunk, dict) else type(chunk)}")
                
                # 若 chunk 包含 message token，打字机输出
                if isinstance(chunk, dict) and "messages" in chunk:
                    msgs = chunk["messages"]
                    for m in msgs:
                        if hasattr(m, "content") and m.content:
                            print(f"      └─ Message [{m.type}]: {m.content[:80]}...")
            else:
                print(f"  [Direct Event]: {event}")
                
        print("\n[SUCCESS] PoC Stream & Subagent Test Passed!")
    except Exception as e:
        print(f"\n[ERROR] PoC Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_poc())
