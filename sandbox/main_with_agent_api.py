from langchain.agents import create_structured_chat_agent, AgentExecutor, initialize_agent, AgentType
from langchain_deepseek import ChatDeepSeek
from web_search_tool import google_search_tool
import os

api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
llm = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
)

tools = [google_search_tool]

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # 关键：使用 ReAct Agent
    verbose=True,  # 输出推理和工具调用过程
    handle_parsing_errors=True
)
response = agent.invoke({"input": "今天有哪些国际新闻？"})
print(response)
