# Empirical verification of StreamPart ns structure (main graph vs nested subgraph)
import asyncio
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

class State(TypedDict):
    messages: Annotated[list, add_messages]

def child_node(state):
    return {"messages": [{"role": "assistant", "content": "child reply"}]}

child = StateGraph(State)
child.add_node("child_model", child_node)
child.add_edge(START, "child_model")
child.add_edge("child_model", END)
child_compiled = child.compile()

def parent_node(state):
    # simulate a main-graph tool call: emit a custom event
    print("PARENT-TOOL-LIKE custom event", flush=True)
    return {"messages": [{"role": "assistant", "content": "main reply"}]}

def subgraph_caller_node(state):
    # this node runs inside the main graph "tools" node in real agents;
    # here we invoke a nested graph from inside a node to simulate a subagent
    result = child_compiled.invoke({"messages": [{"role": "human", "content": "sub in"}]})
    return {"messages": result["messages"]}

g = StateGraph(State)
g.add_node("tools", subgraph_caller_node)
g.add_edge(START, "tools")
g.add_edge("tools", END)
compiled = g.compile()

async def main():
    chunks = []
    async for chunk in compiled.astream(
        {"messages": [{"role": "human", "content": "hi"}]},
        stream_mode=["updates", "custom"],
        subgraphs=True,
        version="v2",
    ):
        chunks.append(chunk)
    for c in chunks:
        print(f"type={c['type']!r} ns={c['ns']!r} data_keys={list(c['data'].keys()) if isinstance(c['data'], dict) else type(c['data']).__name__}")

asyncio.run(main())
