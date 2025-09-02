import json
import re
import uuid
from typing import Any, Dict, List
from langchain_core.messages import AIMessage
from agent.tools.date.date_tool import date_diff_days, date_diff_hint

# --------------------------
# 规划状态辅助
# --------------------------
def ensure_planning_state(state: Dict[str, Any]) -> Dict[str, Any]:
    pl = dict(state.get("planning") or {})
    if "tried_count" not in pl:
        pl["tried_count"] = 0
    if "max_retry" not in pl:
        pl["max_retry"] = 3
    if "tried_urls" not in pl:
        pl["tried_urls"] = []
    if "enable" not in pl:
        pl["enable"] = False
    # 记录无效的tool_call_id，避免重复调用或被模型看到
    if "invalid_tool_call_ids" not in pl:
        pl["invalid_tool_call_ids"] = []
    # 兜底状态：进入后切换到无工具模型，防止后续继续发工具
    if "exhausted" not in pl:
        pl["exhausted"] = False
    return pl

def reset_planning(pl: Dict[str, Any]) -> Dict[str, Any]:
    """
    仅重置计数与已尝试链接；exhausted/enable/invalid_tool_call_ids 由调用方按需控制。
    """
    pl["tried_count"] = 0
    pl["tried_urls"] = []
    return pl

# --------------------------
# planning 节点类
# --------------------------
class PlanningNode:
    def __init__(self, llm_instance, date_tool):
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
            tool_calls = None
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls = msg.tool_calls
            elif hasattr(msg, "additional_kwargs") and "tool_calls" in msg.additional_kwargs:
                tool_calls = msg.additional_kwargs["tool_calls"]
            if not tool_calls:
                continue
            if any(tc.get("id") == tool_call_id for tc in tool_calls):
                target_tool_calls = tool_calls
                break
        if not target_tool_calls:
            return content, None, tool_call_id
        for item in target_tool_calls:
            if item.get("id") == tool_call_id:
                fn = item.get("function", {}) or {}
                args_raw = fn.get("arguments")
                url = None
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                        url = args.get("url")
                    except Exception:
                        url = None
                elif isinstance(args_raw, dict):
                    url = args_raw.get("url")
                else:
                    url = (item.get("args") or {}).get("url")
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

    # ---- 内部辅助：消息编辑
    @staticmethod
    def _remove_url_summary_by_id(messages: List[Any], target_id: str) -> List[Any]:
        return messages

    @staticmethod
    def _mark_unselectable(search_results: List[Dict[str, Any]], url: str):
        for item in search_results:
            if item.get("link") == url:
                item["selectable"] = False
        return search_results

    # ---- 节点可调用入口 ----
    def __call__(self, state: Dict[str, Any]):
        messages = state["messages"]
        pl = ensure_planning_state(state)

        # 若已耗尽，直接进入 chatbot（兜底，防止循环）
        if pl.get("exhausted"):
            return {"next": "chatbot", "planning": pl}

        if self._should_judge(messages):
            user_question = self._get_user_question(messages)
            url_summary_results, url, tool_call_id = self._get_url_summary(messages)
            print("url=", url)
            print("tool_call_id=", tool_call_id)

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
                # 记录无效的 url_summary 调用，供 chatbot 过滤
                if tool_call_id and tool_call_id not in pl["invalid_tool_call_ids"]:
                    pl["invalid_tool_call_ids"].append(tool_call_id)
                    print(f"[planning] 标记无效 tool_call_id={tool_call_id}")

                if url:
                    if url not in pl["tried_urls"]:
                        pl["tried_urls"].append(url)
                    search_results = self._mark_unselectable(search_results, url)

                # 兜底1：达到最大重选次数 -> 停止 planning，进入 chatbot（避免无限循环）
                if pl["tried_count"] >= pl["max_retry"]:
                    print(f"[planning] 已达到最大重选次数({pl['max_retry']})，停止重选，进入chatbot（无工具）")
                    pl["exhausted"] = True
                    pl["enable"] = False
                    next_node = "chatbot"
                    return {"next": next_node, "planning": pl}

                # 兜底2：无可选搜索结果 -> 停止 planning
                if not search_results:
                    print("[planning] 无可用搜索结果，停止重选，进入chatbot（无工具）")
                    pl["exhausted"] = True
                    pl["enable"] = False
                    next_node = "chatbot"
                    return {"next": next_node, "planning": pl}

                choose_index = self._llm_select_next_url(
                    user_question=user_question,
                    search_results=search_results,
                    tried_urls=pl["tried_urls"],
                    date=today_str,
                )
                if choose_index == -1:
                    print("[planning] LLM判定没有合适链接，停止重选，进入chatbot（无工具）")
                    pl["exhausted"] = True
                    pl["enable"] = False
                    next_node = "chatbot"
                    return {"next": next_node, "planning": pl}

                # 正常重选：触发新的 url_summary（仅返回增量消息，避免重复追加）
                next_url = search_results[choose_index].get("link")
                print(f"[planning] LLM选择第{choose_index}个google_search结果: {next_url}")
                new_tool_call_id = f"call_{uuid.uuid4()}"
                new_msg = AIMessage(
                    content='',
                    additional_kwargs={
                        "tool_calls": [
                            {
                                "id": new_tool_call_id,
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
                pl["tried_count"] += 1
                next_node = "tools"
                return {"next": next_node, "messages": [new_msg], "planning": pl}
        else:
            next_node = "chatbot"

        # 其余路径不返回 messages，避免重复追加
        return {"next": next_node, "planning": pl}