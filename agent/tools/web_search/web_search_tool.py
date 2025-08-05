import re
import os
import requests
from langchain.tools import Tool
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from ..web_search.authority import calculate_authority_score
from ..web_search.freshness import calculate_freshness_score, extract_date_from_snippet
from ..web_search.relevance import calculate_relevance_score
from ..web_search.sensitive_filter import filter_sensitive_results, filter_blocked_domains

class GetSearchSchema(BaseModel):
    query: str = Field(description="使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。")

@tool(args_schema=GetSearchSchema)
def google_search(query: str, max_results: int = 30) -> list:
    """
    使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。输入的问题应该简洁明了，避免使用复杂的语句。
    注意每个项目返回的发布日期是否为用户所需的日期，特别是当用户询问“今天”、“明天”或“后天”等时，确保返回的日期与用户期望一致。
    """
    print(f"google_search called with query: {query}, max_results: {max_results}")
    url = "https://www.googleapis.com/customsearch/v1"
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("SEARCH_ENGINE_ID")
    proxies = {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }

    refs = []
    num_per_page = 10
    for start in range(1, max_results + 1, num_per_page):
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": num_per_page,
            "start": start,
            "lr": "lang_zh",
            "sort": "date",
            "safe": "active"
        }

        response = requests.get(
            url=url,
            params=params,
            proxies=proxies,
            timeout=15
        )
        data = response.json()
        items = data.get("items", [])
        if not items:
            break
        for i, item in enumerate(items, 1):
            refs.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
            if len(refs) >= max_results:
                break
        if len(refs) >= max_results:
            break

    if not refs:
        refs.append({
            "title": "无搜索结果",
            "link": "",
            "snippet": "未查到与您的问题相关的网页信息。"
        })
    refs = filter_sensitive_results(refs)
    refs = filter_blocked_domains(refs)
    if refs is None or len(refs) == 0:
        refs.append({
            "title": "无搜索结果",
            "link": "",
            "snippet": "未查到与您的问题相关的网页信息。"
        })
    sorted = sort_search_results(refs, query)
    print("sorted:", sorted)

    return sorted

google_search_tool = Tool(
    name="google_search",
    func=google_search,
    description="使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。"
)

SEARCH_TYPE_WEIGHTS = {
    "news":      {"freshness": 0.6, "authority": 0.2, "relevance": 0.2},
    "weather":   {"freshness": 0.7, "authority": 0.2, "relevance": 0.1},
    "academic":  {"freshness": 0.1, "authority": 0.7, "relevance": 0.2},
    "qa":        {"freshness": 0.2, "authority": 0.1, "relevance": 0.7},
    "product":   {"freshness": 0.2, "authority": 0.2, "relevance": 0.6},
    "default":   {"freshness": 0.4, "authority": 0.2, "relevance": 0.4},
}

def detect_search_type(query):
    mapping = [
        ("天气|气温|温度|空气质量|pm2.5|台风|下雨|天气预报", "weather"),
        ("新闻|快讯|头条|breaking news|最新消息|报道", "news"),
        ("论文|cite|引用|sci|nature|science|arxiv|学者|学术|实验|研究|综述", "academic"),
        ("怎么|如何|原因|为什么|原理|教程|指南|经验|比较|哪个好|测评|对比|游戏", "qa"),
        ("买|价格|优惠|促销|性价比|评测|购物|产品", "product"),
    ]
    for pattern, stype in mapping:
        if re.search(pattern, query, re.I):
            return stype
    return "default"

def sort_search_results(results, query):
    """根据相关性和权威性对搜索结果进行排序"""
    search_type = detect_search_type(query)
    weights = SEARCH_TYPE_WEIGHTS.get(search_type, SEARCH_TYPE_WEIGHTS["default"])
    for item in results:
        authority_score = calculate_authority_score(item['link'])
        freshness_score = calculate_freshness_score(extract_date_from_snippet(item['snippet']))
        relevance_score = calculate_relevance_score(item, query)
        total_score = (
                relevance_score * weights["relevance"] +
                authority_score * weights["authority"] +
                freshness_score * weights["freshness"]
        )
        item['score'] = round(total_score, 2)

    # 按总分降序排序
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    return sorted_results