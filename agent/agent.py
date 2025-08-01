from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START
from langchain_deepseek import ChatDeepSeek
import os
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from agent.tools.date.date_tool import today_date
from agent.tools.spider.spider_tool import url_summary
from agent.tools.web_search.web_search_tool import google_search

# 定义了状态图
graph_builder = StateGraph(MessagesState)

tools = [today_date, google_search, url_summary]
tool_node = ToolNode(tools)

### 定义模型和 chatbot 节点
api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
llm = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
)
llm = llm.bind_tools(tools)
sys_msg = SystemMessage(content=
"""
你是一个智能检索助手，必须严格遵守以下操作规则：
**时间处理规则**\n
1. 当问题包含'今天'、'当前'、'最近'、'最新'等时间词时，必须第一步调用 today_date 工具获取当前日期\n
2. 基于获取的日期计算其他时间（如明天=今天+1天），不要自行猜测日期\n\n

**搜索执行规则**\n
1. 遇到以下情况必须使用 google_search：\n
- 涉及实时信息（天气/新闻/股票）\n
- 特定产品/游戏/事件的详细指南\n"
- 2024年7月之后发生的事件\n
2. 搜索时使用自然时间词而非具体日期（如搜'今天温州天气'而非'2025年7月21日温州天气'）\n"
3. 从搜索结果中筛选1-3个最相关链接\n\n
4. 如果是实时信息，搜索结果的日期必须与用户问题中的时间概念一致（如“今天”、“明天”等），否则需要重新搜索。
5. 如果没有合适的搜索结果，修改搜索关键词进行重新搜索。

**网页摘要规则**\n
1. 只有通过google_search获取链接后才能使用url_summary\n"
2. 对每个选中的链接单独调用url_summary\n\n
3. 如果get_summary返回的内容与用户问题不相关，重新选择一个链接再次调用url_summary。
4. 在选取某个链接进行url_summary之前，检查snippet中的日期是否与用户问题中的时间概念一致（如“今天”、“明天”等），如果是实时信息，例如：'新闻'，'天气'，'股票'等，必须确保日期一致，否则需要重新选择链接。
5. 选取1-3个最相关的链接进行摘要，确保每个链接的内容都与用户问题相关。如果信息还不够，那么选取更多。

**用户指令规则**
1. 如果用户问题包含类似‘使用网络搜索’的内容，必须使用 google_search 工具进行搜索。
2. 如果用户提供了一个链接，并且期望你介绍该网页的内容，那么使用 url_summary 工具获取该链接的摘要。

**总结回答规则**
1. 如果本次回答使用了google_search或url_summary工具，必须在回答中包含相关链接。
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
config = {"configurable":{"thread_id":"1"}}

def agent_respond(user_input: str) -> str:
    """核心对话接口，自动维护多轮历史（基于 MemorySaver 的 thread_id）"""
    state = {"messages": [("user", user_input)]}
    response = ""
    for event in graph.stream(state, config):
        for value in event.values():
            msg = value["messages"][-1]
            # 支持消息对象和字符串
            if hasattr(msg, "content"):
                response = msg.content
            else:
                response = str(msg)
    return response

def agent_respond_stream(user_input: str):
    state = {"messages": [("user", user_input)]}
    for event in graph.stream(state, config):
        for node, value in event.items():
            if node == "tools":
                tool_msg = value.get("messages", [])[-1] if value.get("messages") else None
                if tool_msg:
                    entry = {
                        "type": "tool_result",
                        "tool": getattr(tool_msg, "name", "unknown"),
                        "content": getattr(tool_msg, "content", str(tool_msg)),
                        "meta": {
                            "tool_call_id": getattr(tool_msg, "tool_call_id", None),
                            "id": getattr(tool_msg, "id", None),
                        }
                    }
                    yield entry
            elif node == "chatbot":
                bot_msg = value.get("messages", [])[-1]
                entry = {
                    "type": "chat",
                    "role": getattr(bot_msg, "role", "assistant"),
                    "content": getattr(bot_msg, "content", str(bot_msg))
                }
                yield entry

if __name__ == "__main__":
    import json
    while True:
        user_input = input("用户> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break
        for entry in agent_respond_stream(user_input):
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            if entry["type"] == "chat":
                print(f'[CHATBOT] {entry["content"]}', flush=True)
            elif entry["type"] == "tool_result":
                print(f'[TOOL: {entry["tool"]}] {entry["content"]}', flush=True)
