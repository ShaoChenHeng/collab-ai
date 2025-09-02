from typing import TypedDict, Annotated, Any, Dict, List
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage
from langgraph.graph.message import add_messages
from agent.tools.date.date_tool import today_date
from agent.tools.spider.spider_tool import url_summary
from agent.tools.web_search.web_search_tool import google_search
import os, json, re
from agent.nodes.planning import PlanningNode, ensure_planning_state

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
# 过滤掉 messages 中无效/不需要的 ToolMessage 和其触发的 AIMessage
# --------------------------
def filter_messages_for_prompt(messages: List[Any], pl: Dict[str, Any]) -> List[Any]:
    invalid_ids = set(pl.get("invalid_tool_call_ids", []))
    exhausted = bool(pl.get("exhausted"))
    filtered = []
    for msg in messages:
        # 过滤 ToolMessage
        if hasattr(msg, "type") and msg.type == "tool":
            tname = getattr(msg, "name", "")
            tid = getattr(msg, "tool_call_id", None)
            # 兜底阶段：直接屏蔽所有 url_summary 的工具结果，避免对话被错误摘要污染
            if exhausted and tname == "url_summary":
                continue
            # 常规：屏蔽已标记无效的 tool_call_id
            if tid in invalid_ids:
                continue

        # 过滤触发工具的 AIMessage
        if isinstance(msg, AIMessage):
            tool_calls = None
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls = msg.tool_calls
            elif hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
                tool_calls = msg.additional_kwargs["tool_calls"]

            if tool_calls:
                # 兜底阶段：凡包含 url_summary 的调用，直接过滤
                if exhausted and any(
                    ((tc.get("function") or {}).get("name") == "url_summary")
                    for tc in tool_calls
                ):
                    continue
                # 常规：若任一调用 id 在 invalid 列表，则过滤该条 AIMessage
                if any(tc.get("id") in invalid_ids for tc in tool_calls):
                    continue

        filtered.append(msg)
    return filtered

def _pretty_messages(msgs: List[Any]) -> List[Dict[str, Any]]:
    out = []
    for i, m in enumerate(msgs):
        row = {"idx": i, "py_type": type(m).__name__}
        if isinstance(m, tuple) and m[0] == "user":
            row.update({"kind": "user", "content": (m[1] if isinstance(m[1], str) else str(m[1]))[:80]})
        elif hasattr(m, "type") and getattr(m, "type", None) == "tool":
            row.update({
                "kind": "tool",
                "name": getattr(m, "name", ""),
                "tool_call_id": getattr(m, "tool_call_id", None)
            })
        elif isinstance(m, AIMessage):
            tool_calls = None
            if hasattr(m, "tool_calls") and m.tool_calls:
                tool_calls = m.tool_calls
            elif hasattr(m, "additional_kwargs") and "tool_calls" in m.additional_kwargs:
                tool_calls = m.additional_kwargs["tool_calls"]
            row.update({
                "kind": "ai",
                "has_tool_calls": bool(tool_calls),
                "tool_call_ids": [tc.get("id") for tc in tool_calls] if tool_calls else []
            })
        else:
            row.update({"kind": "other"})
        out.append(row)
    return out

def _removed_tool_call_ids(before: List[Any], after: List[Any]) -> List[str]:
    def collect_ids(ms):
        ids = set()
        for m in ms:
            if hasattr(m, "type") and getattr(m, "type", None) == "tool":
                if getattr(m, "tool_call_id", None):
                    ids.add(getattr(m, "tool_call_id"))
            if isinstance(m, AIMessage):
                tool_calls = None
                if hasattr(m, "tool_calls") and m.tool_calls:
                    tool_calls = m.tool_calls
                elif hasattr(m, "additional_kwargs") and "tool_calls" in m.additional_kwargs:
                    tool_calls = m.additional_kwargs["tool_calls"]
                if tool_calls:
                    for tc in tool_calls:
                        if tc.get("id"):
                            ids.add(tc["id"])
        return ids
    return sorted(list(collect_ids(before) - collect_ids(after)))

# --------------------------
# chatbot 节点
# --------------------------
def chatbot(state: AgentState):
    pl = ensure_planning_state(state)
    before = state["messages"]
    after = filter_messages_for_prompt(before, pl)

    # exhausted=True 时使用无工具模型与无工具系统提示
    model = llm_no_tools if pl.get("exhausted") else llm
    sys_used = sys_msg_no_tools if pl.get("exhausted") else sys_msg

    # 调试日志
    # try:
    #     import json as _json
    #     print(f"[chatbot] invalid_tool_call_ids={pl.get('invalid_tool_call_ids')}, exhausted={pl.get('exhausted')}, enable={pl.get('enable')}")
    #     print(f"[chatbot] before_count={len(before)}, after_count={len(after)}, "
    #           f"removed_tool_call_ids={_removed_tool_call_ids(before, after)}")
    #     print("[chatbot] before_summary=", _json.dumps(_pretty_messages(before), ensure_ascii=False, indent=2))
    #     print("[chatbot] after_summary=", _json.dumps(_pretty_messages(after), ensure_ascii=False, indent=2))
    # except Exception:
    #     pass

    reply = model.invoke([sys_used] + after)

    # 无工具模式下：清洗任何“工具标记”文本，避免出现 <｜tool▁calls▁begin｜>… 这样的输出
    if pl.get("exhausted"):
        def _strip_tool_markup(s: str) -> str:
            if not isinstance(s, str):
                return s
            return re.sub(r"<｜tool▁calls▁begin｜>.*?<｜tool▁calls▁end｜>", "", s, flags=re.DOTALL).strip()

        cleaned = _strip_tool_markup(getattr(reply, "content", str(reply)))
        cleaned = cleaned or "当前无法继续调用工具检索，我将基于已知信息作答。如需我继续搜索，请重新提问或允许继续检索。"
        # 确保不携带 tool_calls
        reply = AIMessage(content=cleaned)

    return {"messages": [reply]}


# --------------------------
# select 节点
# --------------------------
def select(state: AgentState):
    pl = ensure_planning_state(state)
    next_node = "planning" if pl.get("enable") and not pl.get("exhausted") else "chatbot"
    return {"next": next_node, "planning": pl}

# --------------------------
# 外部交互接口
# --------------------------
def agent_respond(user_input: str, options=None) -> str:
    """
    核心对话接口，自动维护多轮历史（基于 MemorySaver 的 thread_id）
    """
    enable_planning = bool(options.get("enable_planning")) if isinstance(options, dict) else False
    init_state: AgentState = {
        "messages": [("user", user_input)],
        "planning": {
            "enable": enable_planning,
            "exhausted": False,
            "tried_count": 0,
            "tried_urls": [],
            "invalid_tool_call_ids": []
        }
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
    fn = tc.get("function", {}) or {}
    args_raw = fn.get("arguments")
    args = {}
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except Exception:
            args = {}
    elif isinstance(args_raw, dict):
        args = args_raw
    print("[query]", args.get("query"))
    return args.get("query")

def agent_respond_stream(user_input: str, deep_thinking: bool = False):
    """
    启用 deep_thinking=True 时，会在本轮对话内开启 planning 节点。
    """
    init_state: AgentState = {
        "messages": [("user", user_input)],
        "planning": {
            "enable": deep_thinking,
            "exhausted": False,
            "tried_count": 0,
            "tried_urls": [],
            "invalid_tool_call_ids": []
        }
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
# --------------------------
# 工具与模型
# --------------------------
tools = [today_date, google_search, url_summary]
tool_node = ToolNode(tools)

api_key = os.getenv("DEEPSEEK_API_KEY_FROM_ENV")
# 无工具方案的关键：保留一个“未绑定工具”的模型实例，用于兜底阶段
llm_base = ChatDeepSeek(
    api_base="https://api.deepseek.com",  # 或 https://api.deepseek.com/v1
    api_key=api_key,
    model="deepseek-chat",
)
llm = llm_base.bind_tools(tools)   # 常规使用：允许工具
llm_no_tools = llm_base            # 兜底使用：禁止工具
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
5. 在一轮回答中总google_search的次数不超过3次，滥用google_search会导致程序递归过深，使整个程序崩溃
6. 使用url_summary可以对搜索结果中的链接进行更详细的搜索，如果搜索结果中没有更合适的内容了再开启一次新的google_search搜索，避免滥用

**网页摘要规则**
1. 在选取某个链接进行url_summary之前，检查snippet中的日期是否与用户问题中的**时间概念一致**（如“今天”、“明天”等），如果是实时信息，例如：'新闻'，'天气'，'股票'等，必须确保日期一致，否则需要重新选择链接。
2. 一次只选择一个链接进行url_summary，避免同时调用多个链接
3. 从google_search的搜索结果中筛选1-3个最相关链接进行url_summary进行更详细的搜索，这能够使回答更详细
4. 结合从url_summary获取的摘要内容，回答用户问题。

**用户指令规则**
1. 如果用户问题包含类似‘使用网络搜索’的内容，必须使用 google_search 工具进行搜索。
2. 如果用户提供了一个链接，并且期望你介绍该网页的内容，那么使用 url_summary 工具获取该链接的摘要。

**总结回答规则**
1. 如果本次回答使用了google_search或url_summary工具，必须在回答中包含相关链接。
"""
)
sys_msg_no_tools = SystemMessage(content=
"""
你现在处于兜底阶段，禁止调用任何工具（包括 today_date、google_search、url_summary）。
要求：
- 不要输出任何“工具调用格式”或函数调用标记（例如 <｜tool▁calls▁begin｜>…）
- 不要提出“让我去打开/访问/调用工具”的建议
- 只能基于当前对话中的可见信息进行总结与回答
- 如果信息不足，请直接说明“由于无法继续检索，无法进一步确认”，并给出你能提供的建议或让用户澄清
- 输出必须是纯文本自然语言，直接给出结论/要点，而不是操作计划
"""
)

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
