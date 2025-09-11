import re
import json
from typing import TypedDict, Annotated, Any, Dict, List

from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage

from agent.nodes.planning import PlanningNode, ensure_planning_state
from agent.utils import prewarm
from agent.utils.message import filter_messages_for_prompt, is_final_agent_reply, get_tool_query
from agent import config as agent_config

# --------------------------
# State 定义
# --------------------------
class AgentState(TypedDict, total=False):
    messages: Annotated[List[Any], add_messages]
    next: str
    planning: Dict[str, Any]

# --------------------------
# Graph 节点
# --------------------------
def chatbot(state: AgentState):
    pl = ensure_planning_state(state)
    messages = filter_messages_for_prompt(state["messages"], pl)

    model = agent_config.LLM_NO_TOOLS if pl.get("exhausted") else agent_config.LLM_WITH_TOOLS
    sys_msg = agent_config.SYS_MSG_NO_TOOLS if pl.get("exhausted") else agent_config.SYS_MSG_WITH_TOOLS

    reply = model.invoke([sys_msg] + messages)

    if pl.get("exhausted"):
        def _strip_tool_markup(s: str) -> str:
            if not isinstance(s, str): return s
            return re.sub(r"<｜tool calls begin｜>.*?<｜tool calls end｜>", "", s, flags=re.DOTALL).strip()

        cleaned = _strip_tool_markup(getattr(reply, "content", str(reply)))
        cleaned = cleaned or "当前无法继续调用工具检索，我将基于已知信息作答。如需我继续搜索，请重新提问或允许继续检索。"
        reply = AIMessage(content=cleaned)

    return {"messages": [reply]}


def select(state: AgentState):
    pl = ensure_planning_state(state)
    next_node = "planning" if pl.get("enable") and not pl.get("exhausted") else "chatbot"
    return {"next": next_node, "planning": pl}


# --------------------------
# Graph 构建
# --------------------------
def create_graph():
    graph_builder = StateGraph(AgentState)

    tool_node = ToolNode(agent_config.TOOLS)
    planning_node = PlanningNode(llm_instance=agent_config.LLM_WITH_TOOLS, date_tool=agent_config.TOOLS[0])

    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("planning", planning_node)
    graph_builder.add_node("select", select)

    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "select")
    graph_builder.add_conditional_edges("select", lambda state: state["next"])
    graph_builder.add_conditional_edges("planning", lambda state: state["next"])

    return graph_builder.compile(checkpointer=agent_config.MEMORY)


graph = create_graph()


# --------------------------
# 外部交互接口
# --------------------------
def agent_respond_stream(user_input: str, deep_thinking: bool = False, web_search_mode: str = "auto"):
    init_state: AgentState = {
        "messages": [("user", user_input)],
        "planning": {"enable": deep_thinking, "exhausted": False, "tried_count": 0, "tried_urls": [],
                     "invalid_tool_call_ids": []}
    }
    for event in graph.stream(init_state, agent_config.GRAPH_CONFIG):
        for node, value in event.items():
            if node == "tools":
                tool_msg = value.get("messages", [])[-1] if value.get("messages") else None
                if tool_msg:
                    yield {
                        "type": "tool_result", "tool": getattr(tool_msg, "name", "unknown"),
                        "content": getattr(tool_msg, "content", str(tool_msg)),
                        "meta": {"tool_call_id": getattr(tool_msg, "tool_call_id", None),
                                 "id": getattr(tool_msg, "id", None)},
                        "is_final": False
                    }
            elif node == "chatbot":
                bot_msg = value.get("messages", [])[-1]
                content = getattr(bot_msg, "content", str(bot_msg))
                final = is_final_agent_reply(bot_msg)
                yield {
                    "type": "chat" if final else "intermediate_step",
                    "role": getattr(bot_msg, "role", "assistant"), "content": content,
                    "query": get_tool_query(bot_msg) if hasattr(bot_msg, "tool_calls") else None,
                    "is_final": final
                }

# --------------------------
# 预加载嵌入模型
# --------------------------
prewarm.start()

# --------------------------
# CLI程序入口
# --------------------------
if __name__ == "__main__":
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
            elif entry["type"] == "intermediate_step":
                print(f'[THOUGHT] {entry["content"]}', flush=True)
