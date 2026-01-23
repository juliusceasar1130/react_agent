import dotenv
from langchain.chat_models import init_chat_model
import os

dotenv.load_dotenv()  # 加载当前目录下的 .env 文件

# 大模型初始化
llm = init_chat_model(
    model="deepseek-chat",
    model_provider="deepseek",
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
)

# enbedding模型
from langchain_community.embeddings import DashScopeEmbeddings

# 设置 API Key
os.environ["DASHSCOPE_API_KEY"] = "sk-a94d0433886148c886b28c99c5fc90e7"

# 初始化模型
# 常用模型名：text-embedding-v1, text-embedding-v2, text-embedding-v3
embeddings = DashScopeEmbeddings(model="text-embedding-v3")

# 使用Chromasa进行向量存储
from langchain_chroma import Chroma

vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)

import bs4
from langchain_community.document_loaders import WebBaseLoader

# Only keep post title, headers, and content from the full HTML.
bs4_strainer = bs4.SoupStrainer(class_=("post-title", "post-header", "post-content"))
loader = WebBaseLoader(
    web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
    bs_kwargs={"parse_only": bs4_strainer},
)
docs = loader.load()

assert len(docs) == 1
print(f"Total characters: {len(docs[0].page_content)}")

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Split the text into chunks.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # chunk size (characters)
    chunk_overlap=200,  # chunk overlap (characters)
    add_start_index=True,  # track index in original document
)
all_splits = text_splitter.split_documents(docs)

# Add the documents to the vector store. 运行一次就行
# document_ids = vector_store.add_documents(documents=all_splits)

from langchain.tools import tool


@tool(response_format="content_and_artifact")  # response_format="content_and_artifact"
def retrieve_context(query: str):
    """Retrieve information to help answer a query."""
    retrieved_docs = vector_store.similarity_search(query, k=2)
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\nContent: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs


from langchain.tools import tool

from langchain.agents import create_agent

# 方案1：使用工具
# tools = [retrieve_context]
# # If desired, specify custom instructions
# prompt = (
#     "You have access to a tool that retrieves context from a blog post. "
#     "Use the tool to help answer user queries."
#     "最终回复翻译成中文"
# )
# agent = create_agent(llm, tools, system_prompt=prompt)

# 方案2：使用2 stage
# from langchain.agents.middleware import dynamic_prompt, ModelRequest

# @dynamic_prompt
# def prompt_with_context(request: ModelRequest) -> str:
#     """Inject context into state messages."""
#     last_query = request.state["messages"][-1].text
#     retrieved_docs = vector_store.similarity_search(last_query)

#     docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

#     system_message = (
#         "You are a helpful assistant. Use the following context in your response:"
#         f"\n\n{docs_content}"
#     )

#     return system_message


# agent = create_agent(llm, tools=[], middleware=[prompt_with_context])

# 方案3

from typing import Any
from langchain_core.documents import Document
from langchain.agents.middleware import AgentMiddleware, AgentState


class State(AgentState):
    context: list[Document]


class RetrieveDocumentsMiddleware(AgentMiddleware[State]):
    state_schema = State

    def before_model(self, state: AgentState) -> dict[str, Any] | None:
        last_message = state["messages"][-1]
        retrieved_docs = vector_store.similarity_search(last_message.text)

        docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

        augmented_message_content = (
            f"{last_message.text}\n\n"
            "Use the following context to answer the query:\n"
            f"{docs_content}"
        )
        return {
            "messages": [
                last_message.model_copy(update={"content": augmented_message_content})
            ],
            "context": retrieved_docs,
        }


agent = create_agent(
    llm,
    tools=[],
    middleware=[RetrieveDocumentsMiddleware()],
)

# query = (
#     "What is the standard method for Task Decomposition?\n\n"
#     "Once you get the answer, look up common extensions of that method."
# )

# for event in agent.stream(
#     {"messages": [{"role": "user", "content": query}]},
#     stream_mode="values",
# ):
#     event["messages"][-1].pretty_print()
