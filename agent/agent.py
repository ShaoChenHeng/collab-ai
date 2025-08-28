from typing import TypedDict, Annotated, Any, Dict, List
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage
from langgraph.graph.message import add_messages  # 若报错可改为: from langgraph.graph import add_messages
from agent.tools.date.date_tool import today_date, parse_cn_date, date_diff_days, date_diff_hint
from agent.tools.spider.spider_tool import url_summary
from agent.tools.web_search.web_search_tool import google_search
import os, json, uuid, re

# --------------------------
# State 定义
# --------------------------
class AgentState(TypedDict, total=False):
    # LangGraph 合并消息的 reducer
    messages: Annotated[List[Any], add_messages]
    # 用于条件边控制
    next: str
    # 规划相关的状态，统一收口到这里，避免全局变量
    planning: Dict[str, Any]

# --------------------------
# 工具与模型
# --------------------------
tools = [today_date, google_search, url_summary]
tool_node = ToolNode(tools)

api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
llm = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
).bind_tools(tools)

sys_msg = SystemMessage(content=
"""
你是一个智能检索助手，必须严格遵守以下操作规则：
**时间处理规则**
1. 当问题包含'今天'、'当前'、'最近'、'最新'、'现在'等时间词时，必须第一步调用 today_date 工具获取当前日期
2. 基于获取的日期计算其他时间（如明天=今天+1天），不要自行猜测日期

**搜索执行规则**
1. 遇到以下情况必须使用 google_search：
- 涉及实时信息（天气/新闻/股票）
- 特定产品/游戏/事件的详细指南
- 2024年7月之后发生的事件
2. 搜索时使用自然时间词而非具体日期（如搜'今天温州天气'而非'2025年7月21日 温州天气'）
3. 如果是实时信息，搜索结果的日期必须与用户问题中的时间概念一致（如“今天”、“明天”等），否则需要重新搜索。
4. 关键词尽量短
5. 在一轮回答中总google_search的次数不超过3次，避免过多调用

**网页摘要规则**
1. 在选取某个链接进行url_summary之前，检查snippet中的日期是否与用户问题中的**时间概念一致**（如“今天”、“明天”等），如果是实时信息，例如：'新闻'，'天气'，'股票'等，必须确保日期一致，否则需要重新选择链接。
2. 一次只选择一个链接进行url_summary，避免同时调用多个链接
3. 从搜索结果中筛选1-3个最相关链接进行url_summary进行更详细的搜索，这能够使回答更详细
4. 如果url_summary返回的内容与用户问题不相关、无法获取摘要、网络问题、以及其他错误，重新选择一个链接再次调用url_summary。
5. 结合从url_summary获取的摘要内容，回答用户问题。

**用户指令规则**
1. 如果用户问题包含类似‘使用网络搜索’的内容，必须使用 google_search 工具进行搜索。
2. 如果用户提供了一个链接，并且期望你介绍该网页的内容，那么使用 url_summary 工具获取该链接的摘要。

**总结回答规则**
1. 如果本次回答使用了google_search或url_summary工具，必须在回答中包含相关链接。
"""
)

# --------------------------
# 规划状态辅助
# --------------------------
def ensure_planning_state(state: AgentState) -> Dict[str, Any]:
    pl = dict(state.get("planning") or {})
    if "tried_count" not in pl:
        pl["tried_count"] = 0
    if "max_retry" not in pl:
        pl["max_retry"] = 3
    if "tried_urls" not in pl:
        pl["tried_urls"] = []
    if "enable" not in pl:
        pl["enable"] = False
    return pl

def reset_planning(pl: Dict[str, Any]) -> Dict[str, Any]:
    pl["tried_count"] = 0
    pl["tried_urls"] = []
    return pl

# --------------------------
# chatbot 节点
# --------------------------
def chatbot(state: AgentState):
    return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

# --------------------------
# planning 节点类
# --------------------------
class PlanningNode:
    def __init__(self, llm_instance, date_tool=today_date):
        self.llm = llm_instance
        self.date_tool = date_tool

    # ---- 内部辅助：消息/判断 ----
    @staticmethod
    def _is_user_message(msg) -> bool:
        if isinstance(msg, tuple) and msg[0] == "user":
            return True
        if type(msg).__name__ == "HumanMessage":
            return True
        return False

    def _should_judge(self, messages: List[Any]) -> bool:
        user_idx = None
        for i in range(len(messages)-1, -1, -1):
            if self._is_user_message(messages[i]):
                user_idx = i
                break
        if user_idx is None:
            return False
        current_round_msgs = messages[user_idx+1:]
        found_url_summary = False
        for msg in reversed(current_round_msgs):
            if hasattr(msg, "type") and msg.type == "tool":
                name = getattr(msg, "name", "")
                if name == "url_summary":
                    if found_url_summary:
                        return True
                    found_url_summary = True
                elif name == "google_search" and found_url_summary:
                    return True
        return False

    @staticmethod
    def _get_user_question(messages: List[Any]) -> str:
        for msg in reversed(messages):
            if type(msg).__name__ == "HumanMessage":
                return getattr(msg, "content", "").strip()
            if isinstance(msg, tuple) and msg[0] == "user":
                return msg[1].strip()
        return ""

    @staticmethod
    def _get_url_summary(messages: List[Any], tool_name="url_summary"):
        content = None
        tool_call_id = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "tool" and getattr(msg, "name", "") == tool_name:
                content = getattr(msg, "content", None)
                tool_call_id = getattr(msg, "tool_call_id", None)
                break
        if tool_call_id is None:
            return None, None, None
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

    @staticmethod
    def _get_search_results(messages: List[Any], tool_name="google_search"):
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "tool":
                if getattr(msg, "name", "") == tool_name:
                    if hasattr(msg, "content"):
                        result = msg.content
                    elif hasattr(msg, "result"):
                        result = msg.result
                    else:
                        result = []
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                            print("[get_search_results] 已解析为对象:", type(result))
                        except Exception as e:
                            print("[get_search_results] json.loads失败:", e)
                            result = []
                    return result
        return []

    # ---- 内部辅助：评估/选择 ----
    def _llm_judge_content(self, user_question: str, summary_dict: dict, date: str) -> (bool, str):
        summary = summary_dict.get("summary", "")
        summary_date_str = summary_dict.get("date", "")
        if summary_date_str and date:
            diff_days_text = date_diff_days(summary_date_str, date)
            diff_hint_text = date_diff_hint(diff_days_text)
            date_info = (
                f"网页摘要日期：{summary_date_str}\n"
                f"当前日期：{date}\n"
                f"日期相差：{diff_days_text}天\n"
                f"{diff_hint_text}\n"
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
        if self.llm is None:
            raise ValueError("没有可用的llm实例")
        llm_response = self.llm.invoke(prompt)
        llm_response_text = getattr(llm_response, "content", str(llm_response)).strip()
        print(f"LLM judge_content response: {llm_response_text}\n")
        if llm_response_text.startswith("是"):
            return True, llm_response_text
        if llm_response_text.startswith("否"):
            reason = llm_response_text[1:].lstrip('，,：:').strip()
            return False, reason or "LLM判定该摘要内容无法回答用户问题"
        return False, f"LLM返回无法解析：{llm_response_text}"

    def _judge_content(self, user_question: str, summary_dict: dict, date: str) -> (bool, str):
        result, llm_reason = self._llm_judge_content(user_question, summary_dict, date)
        reason = llm_reason.strip() if llm_reason and llm_reason.strip() else ("内容可以回答用户问题" if result else "LLM判定该网页摘要内容无法回答用户问题")
        print(f"judge_content: LLM判断结果为 {result}, 原因: {reason}")
        return result, reason

    def _llm_select_next_url(self, user_question, search_results, tried_urls, date) -> int:
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
        if self.llm is None:
            raise ValueError("必须传入 llm_instance")
        llm_response = self.llm.invoke(prompt)
        llm_response_text = getattr(llm_response, "content", str(llm_response)).strip()
        print(f"LLM select_next_url response: {llm_response_text}\n")
        match = re.search(r"-?\d+", llm_response_text)
        choose_index = int(match.group()) if match else -1
        invalid = (
            choose_index < 0 or
            choose_index >= len(search_results) or
            search_results[choose_index].get("link") in tried_urls
        )
        if invalid:
            print("LLM输出无效、超范围或选中了已尝试过的链接，自动兜底选分数最高的未尝试项")
            untried = [
                (i, item)
                for i, item in enumerate(search_results)
                if item.get("link") not in tried_urls and item.get("selectable", True)
            ]
            if not untried:
                return -1
            untried.sort(key=lambda x: x[1].get("score", 0), reverse=True)
            choose_index = untried[0][0]
        return choose_index

    # ---- 内部辅助：消息编辑 ----
    @staticmethod
    def _remove_url_summary_by_id(messages: List[Any], target_id: str) -> List[Any]:
        new_messages = []
        for msg in messages:
            if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id", None) == target_id:
                continue
            if hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
                if any(tc.get("id") == target_id for tc in msg.additional_kwargs["tool_calls"]):
                    continue
            if hasattr(msg, "tool_calls"):
                if any(tc.get("id") == target_id for tc in getattr(msg, "tool_calls", [])):
                    continue
            new_messages.append(msg)
        return new_messages

    @staticmethod
    def _mark_unselectable(search_results: List[Dict[str, Any]], url: str):
        for item in search_results:
            if item.get("link") == url:
                item["selectable"] = False
        return search_results

    # ---- 节点可调用入口 ----
    def __call__(self, state: AgentState):
        messages = state["messages"]
        pl = ensure_planning_state(state)

        if self._should_judge(messages):
            user_question = self._get_user_question(messages)
            url_summary_results, url, tool_call_id = self._get_url_summary(messages)
            search_results = self._get_search_results(messages, "google_search")
            today_str = self.date_tool.invoke({})

            for item in search_results:
                item["selectable"] = True

            summary_date = None
            for item in search_results:
                if item.get("link") == url:
                    summary_date = item.get("date", None)
                    break
            url_summary_dict = {"summary": url_summary_results, "date": summary_date}

            is_satisfied, reason = self._judge_content(user_question, url_summary_dict, today_str)
            print(f"[planning] judge_content结果: is_satisfied={is_satisfied}, reason={reason}")

            if is_satisfied:
                next_node = "chatbot"
                pl = reset_planning(pl)
            else:
                if url:
                    pl["tried_urls"].append(url)
                    search_results = self._mark_unselectable(search_results, url)
                messages = self._remove_url_summary_by_id(messages, tool_call_id)
                if pl["tried_count"] >= pl["max_retry"]:
                    print(f"[planning] 已达到最大重选次数({pl['max_retry']})，不再重选，进入chatbot")
                    pl = reset_planning(pl)
                    next_node = "chatbot"
                else:
                    print("[planning] 匹配不合适，准备重选")
                    if search_results and len(search_results) > 0:
                        choose_index = self._llm_select_next_url(
                            user_question=user_question,
                            search_results=search_results,
                            tried_urls=pl["tried_urls"],
                            date=today_str,
                        )
                        if choose_index == -1:
                            print("[planning] LLM判定没有合适链接，进入chatbot")
                            pl = reset_planning(pl)
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
                                                    "arguments": json.dumps({"url": next_url}, ensure_ascii=False),
                                                },
                                                "type": "function",
                                                "index": 0,
                                            }
                                        ],
                                        "refusal": None
                                    }
                                )
                            )
                            pl["tried_count"] += 1
                            next_node = "tools"
                    else:
                        print("[planning] google_search结果不足，无法重试，进入chatbot")
                        pl = reset_planning(pl)
                        next_node = "chatbot"
        else:
            next_node = "chatbot"

        return {"next": next_node, "messages": messages, "planning": pl}

# --------------------------
# select 节点
# --------------------------
def select(state: AgentState):
    pl = ensure_planning_state(state)
    next_node = "planning" if pl.get("enable") else "chatbot"
    return {"next": next_node, "planning": pl}

# --------------------------
# Graph 构建
# --------------------------
graph_builder = StateGraph(AgentState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
planning_node = PlanningNode(llm_instance=llm, date_tool=today_date)
graph_builder.add_node("planning", planning_node)
graph_builder.add_node("select", select)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "select")
graph_builder.add_conditional_edges("select", lambda state: state["next"])
graph_builder.add_conditional_edges("planning", lambda state: state["next"])

memory = MemorySaver()
graph = graph_builder.compile(checkpointer=memory)
config = {
    "recursion_limit": 100,
    "configurable": {"thread_id": "1"}
}

# --------------------------
# 外部交互接口
# --------------------------
def agent_respond(user_input: str, options=None) -> str:
    """
    核心对话接口，自动维护多轮历史（基于 MemorySaver 的 thread_id）
    """
    init_state: AgentState = {
        "messages": [("user", user_input)],
        "planning": {"enable": False}
    }
    response = ""
    for event in graph.stream(init_state, config):
        for value in event.values():
            msg = value["messages"][-1]
            response = getattr(msg, "content", str(msg))
    return response

def is_final_agent_reply(msg):
    if type(msg).__name__ != "AIMessage":
        return False
    has_tool_calls = False
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        has_tool_calls = True
    elif hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
        has_tool_calls = bool(msg.additional_kwargs["tool_calls"])
    return not has_tool_calls and bool(msg.content and msg.content.strip())

def get_tool_query(tool_msg):
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
    """
    启用 deep_thinking=True 时，会在本轮对话内开启 planning 节点。
    """
    init_state: AgentState = {
        "messages": [("user", user_input)],
        "planning": {"enable": deep_thinking}
    }
    for event in graph.stream(init_state, config):
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
    import json as _json
    while True:
        user_input = input("用户> ")
        if user_input.strip().lower() in ("exit", "quit"):
            break
        for entry in agent_respond_stream(user_input):
            print(_json.dumps(entry, ensure_ascii=False), flush=True)
            if entry["type"] == "chat":
                print(f'[CHATBOT] {entry["content"]}', flush=True)
            elif entry["type"] == "tool_result":
                print(f'[TOOL: {entry["tool"]}] {entry["content"]}', flush=True)
            elif entry["type"] == "intermediate_step":
                print(f'[THOUGHT] {entry["content"]}', flush=True)