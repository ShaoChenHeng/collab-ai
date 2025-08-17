import requests
from bs4 import BeautifulSoup
import re
from langchain.tools import Tool
from langchain_core.tools import tool
from pydantic import Field, BaseModel

# 定义需要过滤的正则表达式列表（支持行开头和行中匹配）
REMOVE_PATTERNS = [
    r'^继续阅读.*',
    r'^相关阅读.*',
    r'^©.*',
    r'^版权声明.*',
    r'^联系我们.*',
    r'^免责声明.*',
    r'^如需转载请.*',
    r'^本文图片.*',
    r'^责任编辑.*',
    r'^（原标题：.*）',
    r'^作者：.*',
    r'^来源：.*',
    r'^【.*?】',             # 常见新闻头部
    r'^更多精彩内容.*',
    r'^（.*?）',             # 可能的括号注释
    r'^\s*$',                # 空行
]

def clean_text(text):
    """对文本按行过滤无关内容"""
    filtered_lines = []
    for line in text.splitlines():
        # 检查本行是否匹配任何移除模式
        if any(re.match(pattern, line.strip()) for pattern in REMOVE_PATTERNS):
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines)

# 提取发布日期的函数
def extract_pub_date(soup, text):
    # 先从meta和常见标签找
    # 1. meta tag
    meta_names = ["pubdate", "publishdate", "published_time", "date", "created", "article:published_time", "article:published"]
    for meta in soup.find_all("meta"):
        meta_name = meta.get("name", "").lower() or meta.get("property", "").lower()
        if meta_name in meta_names:
            date_content = meta.get("content", "")
            if date_content and re.search(r"\d{4}[-年./]\d{1,2}[-月./]\d{1,2}", date_content):
                return date_content

    # 2. <time>标签
    for t in soup.find_all("time"):
        tstr = t.get("datetime", "") or t.text
        if re.search(r"\d{4}[-年./]\d{1,2}[-月./]\d{1,2}", tstr):
            return tstr

    # 3. 常见class/id
    date_classes = ["pubtime", "publish-time", "date", "time", "article-date", "article-time"]
    for cls in date_classes:
        for tag in soup.find_all(attrs={"class": re.compile(cls)}):
            if tag.text and re.search(r"\d{4}[-年./]\d{1,2}[-月./]\d{1,2}", tag.text):
                return tag.text
        for tag in soup.find_all(attrs={"id": re.compile(cls)}):
            if tag.text and re.search(r"\d{4}[-年./]\d{1,2}[-月./]\d{1,2}", tag.text):
                return tag.text

    # 4. 正文文本查找日期
    match = re.search(r"(20\d{2}[-年./]\d{1,2}[-月./]\d{1,2}(?: \d{2}:\d{2})?)", text)
    if match:
        return match.group(1)
    return ""

def fetch_webpage_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SimpleBot/1.0)"
    }
    proxies = {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }
    resp = requests.get(url, headers=headers, timeout=15, proxies=proxies)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "nav", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body_text = "\n".join(lines)
    pub_date = extract_pub_date(soup, body_text)
    return body_text, pub_date

def simple_summary(text, max_sentences=10):
    """返回文本前max_sentences个句子作为摘要"""
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    summary = "".join(sentences[:max_sentences])
    return summary

# 网页内容摘要工具
class GetSummarySchema(BaseModel):
    url: str = Field(description="需要获取摘要的网页链接")

@tool(args_schema=GetSummarySchema)
def url_summary(url):
    """
    输入一个网页URL，返回该网页的关键内容摘要。输入应为需要获取摘要的网页链接。
    当你从 google_search_tool 获得的结果标题或摘要与用户问题高度相关时，
    调用本工具获取详细内容，否则你的回答会不完整。
    """
    try:
        text, pub_date = fetch_webpage_text(url)
        summary = simple_summary(text)
        cleaned = clean_text(summary)
        if pub_date:
            return f"发布时间: {pub_date}\n{cleaned}"
        else:
            return cleaned
    except Exception as e:
        return f"无法获取摘要：{str(e)}"
