from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from backend.app.config import settings

llm = ChatDeepSeek(
    model=settings.deepseek_model,
    temperature=settings.agent_temperature,
    max_tokens=settings.agent_max_tokens,
    timeout=None,
    max_retries=2,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)

agent = create_agent(
    model=llm,
    tools=[],
)
# result = agent.invoke({"messages": {"role": "user", "content": "上海有什么好玩的"}})
# print(result)
# print(result["messages"][-1].pretty_print())
