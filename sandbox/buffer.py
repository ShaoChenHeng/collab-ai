from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START
from langchain_deepseek import ChatDeepSeek
import os
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import tools_condition
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from datetime import datetime
from spider import url_summary
from web_search_tool import google_search

# 网络搜索工具
class GetSearchSchema(BaseModel):
    query: str = Field(description="使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。")

@tool(args_schema=GetSearchSchema)
def get_search(query:str) -> list:
    """
    使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。输入的问题应该简洁明了，避免使用复杂的语句。
    注意每个项目返回的发布日期是否为用户所需的日期，特别是当用户询问“今天”、“明天”或“后天”等时，确保返回的日期与用户期望一致。
    """
    return google_search(query)

# 网页内容摘要工具
class GetSummarySchema(BaseModel):
    url: str = Field(description="需要获取摘要的网页链接")

@tool(args_schema=GetSummarySchema)
def get_summary(url:str) -> str:
    """
    输入一个网页URL，返回该网页的关键内容摘要。输入应为需要获取摘要的网页链接。
    当你从 google_search_tool 获得的结果标题或摘要与用户问题高度相关时，
    调用本工具获取详细内容，否则你的回答会不完整。
    """
    return url_summary(url)

# 日期工具
class GetDateSchema(BaseModel):
    pass

@tool(args_schema=GetDateSchema)
def get_date() -> list:
    """
    必须调用此工具的情况：
    1. 用户问题包含'今天'、'当前日期'、'哪天'等时间相关词
    2. 需要基准时间处理'过去'或'未来'相关概念
    返回格式: YYYY年MM月DD日
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    return today


# 定义了状态图
graph_builder = StateGraph(MessagesState)

tools = [get_date, get_search, get_summary]
tool_node = ToolNode(tools)

### 定义模型和 chatbot 节点
api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
llm = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
)
llm = llm.bind_tools(tools)
sys_msg = SystemMessage(content="""
你是一个智能检索助手，必须严格遵守以下操作规则：
**时间处理规则**\n
1. 当问题包含'今天'、'当前'、'最近'等时间词时，必须第一步调用 get_date 工具获取当前日期\n
2. 基于获取的日期计算其他时间（如明天=今天+1天），不要自行猜测日期\n\n

**搜索执行规则**\n
1. 遇到以下情况必须使用 get_google：\n
- 涉及实时信息（天气/新闻/股票）\n
- 特定产品/游戏/事件的详细指南\n"
- 2024年7月之后发生的事件\n
2. 搜索时使用自然时间词而非具体日期（如搜'今天温州天气'而非'2025年7月21日温州天气'）\n"
3. 从搜索结果中筛选1-3个最相关链接\n\n
4. 如果是实时信息，搜索结果的日期必须与用户问题中的时间概念一致（如“今天”、“明天”等），否则需要重新搜索。
5. 如果没有合适的搜索结果，修改搜索关键词进行重新搜索。

**网页摘要规则**\n
1. 只有通过get_search获取链接后才能使用get_summary\n"
2. 对每个选中的链接单独调用get_summary\n\n
3. 如果get_summary返回的内容与用户问题不相关，重新选择一个链接再次调用get_summary。

**总结回答规则**
1. 如果本次回答使用了get_search或get_summary工具，必须在回答中包含相关链接。
""")

def chatbot(state: MessagesState):
    return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("tools", 'chatbot')
graph_builder.add_conditional_edges("chatbot", tools_condition)

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)

print(graph.get_graph().draw_ascii())


config = {"configurable":{"thread_id":"1"}}

while True:
    try:
        user_input = input("用户: ")
    except UnicodeDecodeError as e:
        print("输入异常：可能包含非法字符，请重新输入。")
        continue
    if user_input.strip().lower() in ["exit", "quit", "q"]:
        break
    state = {"messages": [("user", user_input)]}
    for event in graph.stream(state, config):
        for value in event.values():
            msg = value["messages"][-1]
            msg.pretty_print()
