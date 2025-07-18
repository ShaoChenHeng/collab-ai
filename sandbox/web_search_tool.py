import os
import requests
from langchain.tools import Tool

def google_search(query: str) -> str:
    url = "https://www.googleapis.com/customsearch/v1"
    num_results = 10
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("SEARCH_ENGINE_ID")

    proxies = {
        "http": "http://127.0.0.1:7897",  # HTTP 代理
        "https": "http://127.0.0.1:7897",  # HTTPS 代理
    }

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_results,
        "lr": "lang_zh",
        "sort": "date"
    }

    response = requests.get(
        url=url,
        params=params,
        proxies=proxies,
        timeout=15
    )
    data = response.json()
    items = data.get("items", [])
    refs = []
    if items:
        for i, item in enumerate(items, 1):
            refs.append({
                "index": i,
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
    else:
        # 没有搜索结果
        refs.append({
            "index": 1,
            "title": "无搜索结果",
            "link": "",
            "snippet": "未查到与您的问题相关的网页信息。"
        })
    return refs

google_search_tool = Tool(
    name="google_search",
    func=google_search,
    description="使用谷歌搜索获取最新信息。输入应为需要搜索的中文问题。"
)