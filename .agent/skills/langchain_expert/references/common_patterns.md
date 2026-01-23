# Common LangChain & LangGraph Architectural Patterns

## 1. Simple RAG (Retrieval Augmented Generation)

Use this pattern for Q&A over specific documents.

### Architecture
`User Query -> Retrieve Docs -> LLM Generate -> Answer`

### LangGraph Implementation
```python
from langgraph.graph import StateGraph, END

def retrieve(state):
    # Use your retriever here
    docs = retriever.invoke(state["query"])
    return {"documents": docs}

def generate(state):
    # Passes context + query to LLM
    response = chain.invoke(state)
    return {"messages": [response]}

workflow = StateGraph(State)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
```

## 2. Tool Calling Agent (ReAct)

The standard pattern for an autonomous agent.

### Architecture
`LLM -> Decide Tool -> Execute Tool -> LLM -> Answer`

### LangGraph Implementation
Using the prebuilt `create_react_agent`:
```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

tools = [search_tool, calculator_tool]
model = ChatOpenAI(model="gpt-4o")

agent_executor = create_react_agent(model, tools)
```

## 3. Human-in-the-loop

Use for sensitive actions requiring approval.

### Code Snippet
```python
# Compile with interrupt_before
graph = workflow.compile(interrupt_before=["sensitive_action_node"])

# 1. Run until interruption
thread_config = {"configurable": {"thread_id": "1"}}
graph.invoke(input_data, thread_config)

# 2. (Human verifies) -> Update state if needed
# graph.update_state(thread_config, {"approved": True})

# 3. Resume
graph.invoke(None, thread_config)
```
