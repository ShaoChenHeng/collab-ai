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
1. 当问题包含'今天'、'当前'、'最近'、'最新'、'现在'等时间词时，必须第一步调用 today_date 工具获取当前日期\n
2. 基于获取的日期计算其他时间（如明天=今天+1天），不要自行猜测日期\n\n

**搜索执行规则**\n
1. 遇到以下情况必须使用 google_search：\n
- 涉及实时信息（天气/新闻/股票）\n
- 特定产品/游戏/事件的详细指南\n"
- 2024年7月之后发生的事件\n
2. 搜索时使用自然时间词而非具体日期（如搜'今天温州天气'而非'2025年7月21日 温州天气'）\n"
3. 如果是实时信息，搜索结果的日期必须与用户问题中的时间概念一致（如“今天”、“明天”等），否则需要重新搜索。
4. 关键词尽量短

**网页摘要规则**\n
1. 从搜索结果中筛选1-3个最相关链接进行url_summary进行更详细的搜索，这能够使回答更详细\n\n
2. 如果url_summary返回的内容与用户问题不相关、无法获取摘要、网络问题、以及其他错误，重新选择一个链接再次调用url_summary。
3. 在选取某个链接进行url_summary之前，检查snippet中的日期是否与用户问题中的时间概念一致（如“今天”、“明天”等），如果是实时信息，例如：'新闻'，'天气'，'股票'等，必须确保日期一致，否则需要重新选择链接。
4. 结合从url_summary获取的摘要内容，回答用户问题。

**用户指令规则**
1. 如果用户问题包含类似‘使用网络搜索’的内容，必须使用 google_search 工具进行搜索。
2. 如果用户提供了一个链接，并且期望你介绍该网页的内容，那么使用 url_summary 工具获取该链接的摘要。

**总结回答规则**
1. 如果本次回答使用了google_search或url_summary工具，必须在回答中包含相关链接。
""")

def get_user_question(messages):
    # 优先找最近的有效 HumanMessage
    for msg in reversed(messages):
        # LangChain的 HumanMessage 类型
        if type(msg).__name__ == "HumanMessage":
            question = getattr(msg, "content", "").strip()
            return question
        # 兼容元组格式
        if isinstance(msg, tuple) and msg[0] == "user":
            question = msg[1].strip()
            return question
    return ""

def get_url_summary(messages, tool_name="url_summary"):
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "tool":
            if getattr(msg, "name", "") == "url_summary":
                return msg.content
    return None

def get_search_results(messages, tool_name="google_search"):
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "tool":
            if getattr(msg, "name", "") == tool_name:
                # 假设搜索结果在 msg.content 或 msg.result
                # 你需要根据你的工具定义调整这一行
                if hasattr(msg, "content"):
                    return msg.content  # content里应该是URL列表或者dict
                elif hasattr(msg, "result"):
                    return msg.result
    return []

def is_error_content(summary: str):
    """
    检查网页摘要是否包含错误信息。
    返回：(is_error: bool, error_type: str, error_detail: str)
    """
    error_patterns = [
        # 错误类型, 关键词（可复用正则或简单字符串包含）
        ("ssl_error", ["SSL", "SSLError", "ssl error", "certificate", "UNEXPECTED_EOF_WHILE_READING"]),
        ("connection_error", ["无法连接", "连接失败", "network unreachable", "timed out", "timeout", "连接超时"]),
        ("not_found", ["404", "页面不存在", "not found"]),
        ("server_error", ["502", "503", "504", "服务器错误"]),
        ("empty_content", ["无内容", "empty response", "blank page", "content is empty"]),
        ("access_denied", ["403", "访问受限", "拒绝访问", "需要登录", "robot check", "验证码"]),
        ("tool_extract_error", ["无法获取摘要", "未能获取", "提取失败", "解析失败"]),
        ("unknown_error", ["未知错误", "error", "请求失败"]),
    ]
    if not summary or not summary.strip():
        return True, "empty_content", "内容为空"
    summary_lower = summary.lower()
    for err_type, keywords in error_patterns:
        for kw in keywords:
            if kw.lower() in summary_lower:
                return True, err_type, kw
    return False, "", ""

def llm_judge_content(user_question: str, summary: str, llm_instance=None) -> (bool, str):
    """
    用 LLM 判断 summary 是否能回答 user_question。
    返回 (True/False, 理由: str)
    """
    prompt = f"""
    用户问题：{user_question}
    网页摘要内容：{summary}
    请判断网页摘要内容是否对回答用户问题有参考价值？只要内容有部分帮助或相关信息，也可认为有参考价值。
    只需回答“是”或“否”，并在“否”后补充原因（20字左右）。
    例如：“否”+你的原因 或 “是，摘要和用户问题匹配度高”。"""

    if llm_instance is None:
        llm_instance = llm
    if llm_instance is None:
        raise ValueError("没有可用的llm实例")
    llm_response = llm_instance.invoke(prompt)
    if hasattr(llm_response, "content"):
        llm_response_text = llm_response.content.strip()
    else:
        llm_response_text = str(llm_response).strip()
    print(f"LLM judge_content response: {llm_response_text}\n")
    # 解析结果
    if llm_response_text.startswith("是"):
        return True, ""
    if llm_response_text.startswith("否"):
        # 提取否后面的理由
        reason = llm_response_text[1:].lstrip('，,：:').strip()
        return False, reason or "LLM判定该摘要内容无法回答用户问题"
    # 兜底
    return False, f"LLM返回无法解析：{llm_response_text}"

def llm_select_next_url(user_question, search_results, tried_urls, llm_instance=None):
    """
    用 LLM 从未尝试过的 search_results 中选择最相关的链接。
    返回 url 或 None
    """
    candidates = [r for r in search_results if (r.get("url") if isinstance(r, dict) else r) not in tried_urls]
    if not candidates:
        return None
    # 展示编号和摘要，便于 LLM 选择
    links_text = "\n".join([
        f"编号{i+1}：{c.get('title','')} ({c.get('url', c)})\n摘要：{c.get('snippet','') if isinstance(c, dict) else ''}"
        for i, c in enumerate(candidates)
    ])
    prompt = f"""
    用户问题：{user_question}
    以下是搜索到的网页链接：
    {links_text}
    请从中选出一个最有可能能回答用户问题的编号（只回答编号数字）。如果都不相关，回答0。"""
    if llm_instance is None:
        llm_instance = llm
    llm_response = llm_instance.invoke(prompt)
    response_text = getattr(llm_response, "content", str(llm_response)).strip()
    try:
        idx = int(response_text)
        if idx == 0 or idx > len(candidates):
            return None
        link = candidates[idx - 1]
        return link.get("url") if isinstance(link, dict) else link
    except Exception:
        return None

def judge_content(user_question: str, summary: str, llm_instance=None) -> (bool, str):
    """
    判断 summary 是否能回答 user_question。
    返回 (is_satisfied: bool, reason: str)
    """
    # 1. 错误检测
    is_err, err_type, err_detail = is_error_content(summary)
    if is_err:
        reason = f"网页摘要错误类型: {err_type}，详情: {err_detail}"
        print(f"judge_content: 摘要内容有错误，直接返回False, 原因: {reason}")
        return False, reason

    # 2. LLM 判断
    result, llm_reason = llm_judge_content(user_question, summary, llm_instance)
    if result:
        reason = llm_reason or "内容可以回答用户问题"
    else:
        reason = llm_reason or "LLM判定该网页摘要内容无法回答用户问题"
    print(f"judge_content: LLM判断结果为 {result}, 原因: {reason}")
    return result, reason

def is_user_message(msg) -> bool:
    # tuple 格式
    if isinstance(msg, tuple) and msg[0] == "user":
        return True
    # LangChain HumanMessage
    if type(msg).__name__ == "HumanMessage":
        return True
    # 其他自定义判定
    return False

def should_judge(messages):
    """
    只判断最近一轮（即最后一条用户消息之后）的消息是否需要 judge。
    """
    # 1. 找到最后一条用户消息
    user_idx = None
    for i in range(len(messages)-1, -1, -1):
        if is_user_message(messages[i]):
            user_idx = i
            break
    if user_idx is None:
        # 没有用户消息，说明还没进入对话轮次
        return False

    # 2. 获取本轮消息
    current_round_msgs = messages[user_idx+1:]

    # 3. 查找是否需要 judge（和之前逻辑类似，但只查本轮）
    found_url_summary = False
    for msg in reversed(current_round_msgs):
        if hasattr(msg, "type") and msg.type == "tool":
            name = getattr(msg, "name", "")
            if name == "url_summary":
                if found_url_summary:
                    # 本轮有多次 url_summary，需要 judge
                    return True
                found_url_summary = True
            elif name == "google_search" and found_url_summary:
                # url_summary 前有 google_search，需要 judge
                return True
    return False

def chatbot(state: MessagesState):
    return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

def planning(state):
    messages = state["messages"]
    print("search-results:", get_search_results(messages))
    if should_judge(messages):
        # 1. 用户问题
        user_question = get_user_question(messages)
        # 2. url_summary工具结果
        url_summary_results = get_url_summary(messages)
        # 3. google_search工具结果
        # search_results = get_search_results(messages, "google_search")

        is_satisfied, reason = judge_content(user_question, url_summary_results)
        if is_satisfied:
            next_node = "chatbot"
        else:
            # next_url = None
            print("匹配不合适, 原因：", reason)
            next_node = "chatbot"
            pass
    else:
        next_node = "chatbot"

    return {"next": next_node, "messages": messages, "state": state}

graph_builder = StateGraph(MessagesState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("planning", planning)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "planning")                      # 所有tools输出进planning
graph_builder.add_conditional_edges("planning", lambda state: state["next"])  # planning决定下一步

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
                content = getattr(bot_msg, "content", str(bot_msg))
                if content.startswith("thought:"):
                    entry = {
                        "type": "intermediate_step",
                        "role": getattr(bot_msg, "role", "assistant"),
                        "content": content
                    }
                else:
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
                if entry["type"] == "chat":
                    print(f'[CHATBOT] {entry["content"]}', flush=True)
            elif entry["type"] == "intermediate_step":
                print(f'[THOUGHT] {entry["content"]}', flush=True)
