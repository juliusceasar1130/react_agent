"""
DeepAgent + CompiledSubAgent Stream & v2 Unpacking Minimal PoC Test Script

验证目标：
1. 使用 create_agent / create_deep_agent 构建子智能体与主 Agent
2. 将子智能体作为 CompiledSubAgent(name="sql_domain_agent", description="...", runnable=sql_subagent) 传入 create_deep_agent(subagents=[...])
3. 无需手动显式声明 SubAgentMiddleware，框架内部自动管理 task 委派
4. 运行 astream(..., subgraphs=True, version="v2")，解析 StreamPart 字典解包与 (ns, chunk) 识别
"""
import sys
import os
import asyncio

# 强制设置 UTF-8 标准输出，防止 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 确保 backend 路径能被正常导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.app.agent.llm import _create_llm

# 导入 deepagents 核心与 CompiledSubAgent
from deepagents import create_deep_agent, CompiledSubAgent

print("[PoC] Successfully imported create_deep_agent and CompiledSubAgent.")

# 1. 定义子工具
@tool
def execute_sql_query(query: str) -> str:
    """模拟 SQL 数据库查询工具"""
    print(f"\n   [Subagent SQL Tool Call] 执行 SQL 查询: {query}")
    return f"【SQL 执行结果】查询 '{query}' 成功，返回结果: [{{'department': '底漆车间', 'count': 42}}]"

# 创建大模型实例
llm_instance = _create_llm()

# 2. 构建子 Agent (SQL 领域子智能体)
sql_subgraph = create_deep_agent(
    model=llm_instance,
    tools=[execute_sql_query],
    system_prompt="你是一个 SQL 领域专家智能体，擅长执行 SQL 并汇总结果。",
)

# 3. 包装为 CompiledSubAgent (无需手动写 SubAgentMiddleware)
sql_compiled_subagent = CompiledSubAgent(
    name="sql_domain_agent",
    description="【SQL 领域专家子智能体】专用于处理任何与数据库、SQL 查询、数据统计相关的请求。",
    runnable=sql_subgraph
)

# 4. 构建主 Agent (Main DeepAgent)
checkpointer = MemorySaver()
main_agent = create_deep_agent(
    model=llm_instance,
    subagents=[sql_compiled_subagent], # 👈 直接传入 subagents 参数！
    system_prompt="你是一个通用主智能体，遇到数据查询需求时，请通过 task 工具委派给 sql_domain_agent 处理。",
    checkpointer=checkpointer,
)

async def run_poc():
    print("=" * 60)
    print("[START] CompiledSubAgent + create_deep_agent(subagents=[...]) Stream v2 PoC Test")
    print("=" * 60)
    
    config = {"configurable": {"thread_id": "test_compiled_subagent_thread_001"}}
    input_data = {"messages": [HumanMessage(content="请帮我查询底漆车间当前的在制车数量。")]}
    
    print("\n[Input Query]:", input_data["messages"][0].content)
    print("\n[Streaming Output (subgraphs=True, version='v2')]:")
    
    try:
        # 测试 subgraphs=True, version="v2" 模式下的 StreamPart 解包
        async for chunk in main_agent.astream(
            input_data,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
            version="v2"
        ):
            print(f"\n  [Raw Chunk Type]: {type(chunk)}")
            if isinstance(chunk, dict):
                ns = chunk.get("ns", ())
                chunk_type = chunk.get("type")
                data = chunk.get("data")
                ns_str = " -> ".join(ns) if ns else "main"
                print(f"  [NS: {ns_str}] | Type: {chunk_type}")
                
                if chunk_type == "messages":
                    if isinstance(data, tuple) and len(data) == 2:
                        msg_chunk, metadata = data
                        node = metadata.get("langgraph_node") if isinstance(metadata, dict) else ""
                        if hasattr(msg_chunk, "content") and msg_chunk.content:
                            print(f"      └─ Message [{node}]: {msg_chunk.content}")
                elif chunk_type == "updates":
                    print(f"      └─ Update State Keys: {list(data.keys()) if isinstance(data, dict) else data}")
            elif isinstance(chunk, tuple):
                print(f"  [Tuple Legacy Chunk]: {chunk[:2]}")
            else:
                print(f"  [Other Event]: {chunk}")
                
        print("\n[SUCCESS] CompiledSubAgent v2 Stream PoC Test Passed!")
    except Exception as e:
        print(f"\n[ERROR] PoC Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_poc())
