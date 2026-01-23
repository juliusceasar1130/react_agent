
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.join(os.getcwd()))

try:
    print("Testing imports...")
    from backend.app.services import SQLAgentService
    from backend.app.services_graph import SQLGraphService
    print("Imports successful.")

    print("Initializing SQLAgentService...")
    agent = SQLAgentService()
    print("SQLAgentService initialized.")
    if "ChatOllama" in str(type(agent.agent.agent.llm)):
         print("SQLAgentService is using ChatOllama.")
    else:
         # Depending on how the agent is structured, we might need to dig deeper
         # For create_agent, it wraps it.
         print(f"SQLAgentService LLM type: {type(agent.agent)}")

    print("Initializing SQLGraphService...")
    graph_agent = SQLGraphService()
    print("SQLGraphService initialized.")
    print(f"SQLGraphService LLM type: {type(graph_agent.llm)}")

    if "ChatOllama" in str(type(graph_agent.llm)):
        print("SQLGraphService is using ChatOllama.")

except Exception as e:
    print(f"Error: {e}")
