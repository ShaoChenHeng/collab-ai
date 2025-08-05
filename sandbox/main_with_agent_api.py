from langchain.agents import create_structured_chat_agent, AgentExecutor, initialize_agent, AgentType
from langchain_core.messages import SystemMessage
from langchain_deepseek import ChatDeepSeek
from web_search_tool import google_search_tool
import os
from langchain.tools import BaseTool
from datetime import datetime

class TodayDateTool(BaseTool):
    name: str = "today_date"
    description: str = (
        "始终在遇到‘今天’、‘当前日期’等时间相关问题时，"
        "必须调用此工具来获得标准化的今天日期（YYYY年MM月DD日），"
        "绝不能自己猜测或编造日期。"
    )

    def _run(self, query: str) -> str:
        today = datetime.now().strftime("%Y年%m月%d日")
        return today

    async def _arun(self, query: str) -> str:
        return self._run(query)

api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
llm = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
)

tools = [TodayDateTool(), google_search_tool]

system_message = SystemMessage(
"你是一个智能检索助手。"
"1.如果问题中包含‘今天’、‘当前’等时间词，"
"你必须第一步调用 today_date 工具获取今天日期，"
"然后再根据这个日期进行新闻等相关信息搜索。"
"绝对不要直接假设今天的日期，必须用工具获取。"
"例如："
"用户问：今天有哪些国际新闻？"
"你的第一步应该是：调用 today_date 工具。\n"
)

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # 关键：使用 ReAct Agent
    verbose=True,  # 输出推理和工具调用过程
    handle_parsing_errors=True
)

response = agent.invoke({"input": "今天温州的天气?"})
print(response)
