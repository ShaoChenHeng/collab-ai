from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from agent.tools.date.date_tool import today_date, parse_cn_date, date_diff_days, date_diff_hint
from agent.tools.spider.spider_tool import url_summary
from agent.tools.web_search.web_search_tool import google_search
import os, json, uuid, re

# url-summary 工具的重试次数
global_tried_count = 0
max_retry = 3
tried_urls = []  # 记录已经尝试过但不满意的 google_search 结果索引

tools = [today_date, google_search, url_summary]
tool_node = ToolNode(tools)
enable_planning = False

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
5. 在一轮回答中总google_search的次数不超过3次，避免过多调用\n

**网页摘要规则**\n
1. 在选取某个链接进行url_summary之前，检查snippet中的日期是否与用户问题中的**时间概念一致**（如“今天”、“明天”等），如果是实时信息，例如：'新闻'，'天气'，'股票'等，必须确保日期一致，否则需要重新选择链接。
2. 一次只选择一个链接进行url_summary，避免同时调用多个链接\n
3. 从搜索结果中筛选1-3个最相关链接进行url_summary进行更详细的搜索，这能够使回答更详细\n\n
4. 如果url_summary返回的内容与用户问题不相关、无法获取摘要、网络问题、以及其他错误，重新选择一个链接再次调用url_summary。
5. 结合从url_summary获取的摘要内容，回答用户问题。

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
    content = None
    tool_call_id = None
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "tool" and getattr(msg, "name", "") == tool_name:
            content = getattr(msg, "content", None)
            tool_call_id = getattr(msg, "tool_call_id", None)
            break

    if tool_call_id is None:
        # 统一返回三元组，避免解包错误
        return None, None, None

    url = None
    target_tool_calls = None
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls"):
            tool_calls = msg.tool_calls
        elif isinstance(msg, dict) and "tool_calls" in msg:
            tool_calls = msg["tool_calls"]
        else:
            continue
        if any(tc.get("id") == tool_call_id for tc in tool_calls):
            target_tool_calls = tool_calls
            break
    if not target_tool_calls:
        return content, None, tool_call_id

    for item in target_tool_calls:
        if item.get("id") == tool_call_id:
            url = item.get("args", {}).get("url", None)
            return content, url, tool_call_id

    return content, None, tool_call_id

def get_search_results(messages, tool_name="google_search"):
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "tool":
            if getattr(msg, "name", "") == tool_name:
                # content 可能是 str 或 list/dict
                if hasattr(msg, "content"):
                    result = msg.content
                elif hasattr(msg, "result"):
                    result = msg.result
                else:
                    result = []
                # 如果是字符串，尝试解析 JSON
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                        print("[get_search_results] 已解析为对象:", type(result))
                    except Exception as e:
                        print("[get_search_results] json.loads失败:", e)
                        result = []
                return result
    return []

def llm_judge_content(user_question: str, summary_dict: dict, date: str, llm_instance=None) -> (bool, str):
    """
    用 LLM 判断网页摘要是否能回答用户问题。
    返回 (True/False, 理由: str)
    """

    summary = summary_dict.get("summary", "")
    summary_date_str = summary_dict.get("date", "")
    diff_hint = ""
    diff_days = ""

    # 计算日期差距和提示
    if summary_date_str and date:
        diff_days = date_diff_days(summary_date_str, date)
        diff_hint = date_diff_hint(diff_days)
        date_info = (
            f"网页摘要日期：{summary_date_str}\n"
            f"当前日期：{date}\n"
            f"日期相差：{diff_days}天\n"
            f"{diff_hint}\n"
        )
    else:
        date_info = f"网页摘要日期：{summary_date_str}\n当前日期：{date}\n"

    prompt = (
        f"用户问题：{user_question}\n"
        f"网页摘要内容：{summary}\n"
        f"{date_info}"
        "请判断网页摘要内容是否对回答用户问题有参考价值？只要内容有部分帮助或相关信息，也可认为有参考价值。\n"
        "如用户问题需要实时信息，请结合日期差距综合判断。\n"
        "只需回答“是”或“否”，并在“否”后补充原因（20字左右）。\n"
        "例如：“否、你的原因” 或 “是、你的原因”。\n"
    )

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
        return True, llm_response_text
    if llm_response_text.startswith("否"):
        # 提取否后面的理由
        reason = llm_response_text[1:].lstrip('，,：:').strip()
        return False, reason or "LLM判定该摘要内容无法回答用户问题"
    # 兜底
    return False, f"LLM返回无法解析：{llm_response_text}"

def llm_select_next_url(user_question, search_results, tried_urls, date, llm_instance=None):
    """
    用 LLM 从 search_results 中选出最合适的链接编号（索引）。
    不允许选择 tried_urls 里的链接。
    返回选中的索引（int），如果都不合适返回 -1。
    自动兜底：如果 LLM 选了已尝试过的，则选分数最高的未尝试项（如果有）。
    """
    # 生成 prompt
    prompt = (
        "1. 已尝试过的链接不选，选择最可能回答用户问题的编号（index），只回复数字编号。\n"
        "2. 如果是实时类问题（新闻、天气、股票），那么snippet中的应该和当前日期相近。\n"
        "3. snippet、title、score都是你的评价指标，尽量选择和问题相关的链接。如果所有都不合适请回复-1。\n"
        "4. selectable字段表示该链接是否可以被选中，只有selectable为True的链接才可以被选中。\n"
        f"用户问题：{user_question}\n"
        f"当前日期：{date}\n"
        f"以下是已经尝试过的链接：{tried_urls}\n"
        f"以下是搜索到的网页链接列表：{search_results}\n"
    )

    if llm_instance is None:
        raise ValueError("必须传入 llm_instance")

    # 调用 LLM
    llm_response = llm_instance.invoke(prompt)
    llm_response_text = getattr(llm_response, "content", str(llm_response)).strip()
    print(f"LLM select_next_url response: {llm_response_text}\n")

    # 提取编号（支持“1号”或“选1”等情况），只取第一个数字
    match = re.search(r"-?\d+", llm_response_text)
    choose_index = int(match.group()) if match else -1

    # 检查是否合规
    invalid = (
        choose_index < 0 or
        choose_index >= len(search_results) or
        search_results[choose_index].get("link") in tried_urls
    )
    if invalid:
        print("LLM输出无效、超范围或选中了已尝试过的链接，自动兜底选分数最高的未尝试项")
        print("[search_results] ", search_results)
        print("[tried_urls] ", tried_urls)
        # 只选没尝试过且 selectable 为 True 的项
        untried = [
            (i, item)
            for i, item in enumerate(search_results)
            if item.get("link") not in tried_urls and item.get("selectable", True)
        ]
        if not untried:
            return -1
        print("[untried] ", untried)
        # 按分数降序排序，取第一个
        untried.sort(key=lambda x: x[1].get("score", 0), reverse=True)
        choose_index = untried[0][0]
    return choose_index

def remove_url_summary_by_id(messages, target_id):
    """
    删除 tool_call_id == target_id 的 ToolMessage 和 AIMessage
    """
    new_messages = []
    for msg in messages:
        # ToolMessage
        if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id", None) == target_id:
            continue
        # AIMessage 里 tool_calls
        if hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
            # 如果 tool_calls 里有 id == target_id
            if any(tc.get("id") == target_id for tc in msg.additional_kwargs["tool_calls"]):
                continue
        # 有些实现 tool_calls 直接是 msg.tool_calls
        if hasattr(msg, "tool_calls"):
            if any(tc.get("id") == target_id for tc in getattr(msg, "tool_calls", [])):
                continue
        new_messages.append(msg)
    return new_messages

def mark_unselectable(search_results, url):
    """
    将search_results中所有link==url的项的selectable字段设为False。
    """
    for item in search_results:
        if item.get("link") == url:
            item["selectable"] = False
    return search_results

def judge_content(user_question: str, summary_dict: dict, date: str, llm_instance=None) -> (bool, str):
    """
    判断 summary 是否能回答 user_question。
    返回 (is_satisfied: bool, reason: str)
    """
    result, llm_reason = llm_judge_content(user_question, summary_dict, date, llm_instance)
    # 如果llm_reason有内容（非空且非空白），用它；否则用默认文本
    if llm_reason and llm_reason.strip():
        reason = llm_reason.strip()
    else:
        reason = "内容可以回答用户问题" if result else "LLM判定该网页摘要内容无法回答用户问题"
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
    # print("** IN CHATBOT **", state["messages"])
    return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

def planning(state):
    global global_tried_count, max_retry,tried_urls, llm
    messages = state["messages"]
    #print(messages)

    if should_judge(messages):
        user_question = get_user_question(messages)
        url_summary_results, url, tool_call_id = get_url_summary(messages)
        search_results = get_search_results(messages, "google_search")
        today = today_date.invoke({})
        # 将 search_results 中的每个项都标记为可选
        for item in search_results:
            item["selectable"] = True
        # 给summary添加日期
        summary_date = None
        for item in search_results:
                if item.get("link") == url:
                    summary_date = item.get("date", None)
                    break
        url_summary_dict = {
            "summary": url_summary_results,
            "date": summary_date
        }

        is_satisfied, reason = judge_content(user_question, url_summary_dict, today, llm)
        print(f"[planning] judge_content结果: is_satisfied={is_satisfied}, reason={reason}")

        if is_satisfied:
            next_node = "chatbot"
            global_tried_count = 0
        else:
            tried_urls.append(url)
            search_results = mark_unselectable(search_results, url)
            print("tried_urls:", tried_urls)
            messages = remove_url_summary_by_id(messages, tool_call_id)
            if global_tried_count >= max_retry:
                print(f"[planning] 已达到最大重选次数({max_retry})，不再重选，进入chatbot")
                global_tried_count = 0
                tried_urls = []
                next_node = "chatbot"
            else:
                print("[planning] 匹配不合适，准备重选")
                if search_results and len(search_results) > 0:
                    choose_index = llm_select_next_url(
                        user_question=user_question,
                        search_results=search_results,
                        tried_urls=tried_urls,
                        date=today,
                        llm_instance=llm
                    )
                    if choose_index == -1:
                        print("[planning] LLM判定没有合适链接，进入chatbot")
                        global_tried_count = 0
                        tried_urls = []
                        next_node = "chatbot"
                    else:
                        next_url = search_results[choose_index].get("link")
                        print(f"[planning] LLM选择第{choose_index}个google_search结果: {next_url}")
                        tool_call_id = f"call_{uuid.uuid4()}"
                        messages.append(
                            AIMessage(
                                content='',
                                additional_kwargs={
                                    "tool_calls": [
                                        {
                                            "id": tool_call_id,
                                            "function": {
                                                "name": "url_summary",
                                                "arguments": f'{{"url": "{next_url}"}}'
                                            },
                                            "type": "function",
                                            "index": 0,
                                        }
                                    ],
                                    "refusal": None
                                }
                            )
                        )
                        global_tried_count  = global_tried_count + 1
                        next_node = "tools"
                else:
                    print("[planning] google_search结果不足，无法重试，进入chatbot")
                    global_tried_count = 0
                    tried_urls = []
                    next_node = "chatbot"
    else:
        next_node = "chatbot"

    return {"next": next_node, "messages": messages, "state": state}

def select(state):
    global enable_planning
    messages = state["messages"]
    if enable_planning:
        next_node = "planning"
    else:
        next_node = "chatbot"
    return {"next": next_node, "messages": messages, "state": state}

graph_builder = StateGraph(MessagesState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("planning", planning)
graph_builder.add_node("select", select)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "select")
graph_builder.add_conditional_edges("select", lambda state: state["next"])
graph_builder.add_conditional_edges("planning", lambda state: state["next"])  # planning决定下一步

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
config = {
    "recursion_limit": 100,
    "configurable":{"thread_id":"1"}
}

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

def is_final_agent_reply(msg):
    """
    判断 AIMessage 是否为 agent 的最终自然语言回复。
    """
    if type(msg).__name__ != "AIMessage":
        return False
    # 检查 tool_calls 字段
    has_tool_calls = False
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        has_tool_calls = True
    elif hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
        has_tool_calls = bool(msg.additional_kwargs["tool_calls"])
    return not has_tool_calls and bool(msg.content and msg.content.strip())

def get_tool_query(tool_msg):
    """
    从 AIMessage.tool_calls 提取工具参数（如 google_search 的 query），兼容 dict 或 JSON 字符串格式。
    返回 query 字符串，如无则为 None。
    """
    if not hasattr(tool_msg, "tool_calls") or not tool_msg.tool_calls:
        return None
    tc = tool_msg.tool_calls[0]
    args = tc.get("args", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    print("[query]", args.get("query"))
    return args.get("query")

def agent_respond_stream(user_input: str, deep_thinking: bool = False):
    global enable_planning
    enable_planning = deep_thinking
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
                        },
                        "is_final": False
                    }
                    yield entry
            elif node == "chatbot":
                bot_msg = value.get("messages", [])[-1]
                content = getattr(bot_msg, "content", str(bot_msg))
                final = is_final_agent_reply(bot_msg)
                entry_type = "chat" if final else "intermediate_step"
                query = None
                if hasattr(bot_msg, "tool_calls") and bot_msg.tool_calls:
                    query = get_tool_query(bot_msg)
                entry = {
                    "type": entry_type,
                    "role": getattr(bot_msg, "role", "assistant"),
                    "content": content,
                    "query": query,
                    "is_final": final
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
