from typing import Any, Dict, List
import json
from langchain_core.messages import AIMessage

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
            if exhausted and tname == "url_summary":
                continue
            if tid in invalid_ids:
                continue

        # 过滤触发工具的 AIMessage
        if isinstance(msg, AIMessage):
            tool_calls = msg.tool_calls or msg.additional_kwargs.get("tool_calls", [])
            if tool_calls:
                if exhausted and any(
                    ((tc.get("function") or {}).get("name") == "url_summary")
                    for tc in tool_calls
                ):
                    continue
                if any(tc.get("id") in invalid_ids for tc in tool_calls):
                    continue

        filtered.append(msg)
    return filtered

def is_final_agent_reply(msg: Any) -> bool:
    if not isinstance(msg, AIMessage):
        return False
    has_tool_calls = bool(msg.tool_calls or msg.additional_kwargs.get("tool_calls"))
    return not has_tool_calls and bool(msg.content and msg.content.strip())

def get_tool_query(tool_msg: AIMessage) -> str | None:
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

# --- 调试辅助函数 ---
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