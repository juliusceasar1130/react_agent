import os
import argparse
import sys

def create_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {path}")

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new LangGraph project")
    parser.add_argument("name", help="Name of the project directory")
    parser.add_argument("--path", default=".", help="Base path to create the project in")
    args = parser.parse_args()

    project_dir = os.path.join(args.path, args.name)
    
    if os.path.exists(project_dir):
        print(f"Error: Directory '{project_dir}' already exists.")
        sys.exit(1)

    os.makedirs(project_dir)
    print(f"Created directory: {project_dir}")

    # 1. main.py
    main_content = """from dotenv import load_dotenv
from graph import graph

load_dotenv()

if __name__ == "__main__":
    print("Starting LangGraph Agent...")
    # Example invocation
    result = graph.invoke({"messages": [("user", "Hello world!")]})
    print(result)
"""
    create_file(os.path.join(project_dir, "main.py"), main_content)

    # 2. graph.py
    graph_content = """from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

def chatbot(state: AgentState):
    return {"messages": [("assistant", "Hello! I am a LangGraph agent.")]}

workflow = StateGraph(AgentState)

workflow.add_node("chatbot", chatbot)
workflow.set_entry_point("chatbot")
workflow.add_edge("chatbot", END)

graph = workflow.compile()
"""
    create_file(os.path.join(project_dir, "graph.py"), graph_content)

    # 3. requirements.txt
    req_content = """langchain
langgraph
langchain-openai
python-dotenv
"""
    create_file(os.path.join(project_dir, "requirements.txt"), req_content)

    # 4. .env.example
    env_content = """OPENAI_API_KEY=sk-...
"""
    create_file(os.path.join(project_dir, ".env.example"), env_content)

    print(f"\\nSuccess! usage:\\n  cd {args.name}\\n  pip install -r requirements.txt\\n  python main.py")

if __name__ == "__main__":
    main()
