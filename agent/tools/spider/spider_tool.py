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

def fetch_webpage_text(url):
    """抓取并提取网页正文文本"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SimpleBot/1.0)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    # 移除无用标签
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "nav", "aside"]):
        tag.decompose()

    # 提取正文
    text = soup.get_text(separator="\n")
    # 清理多余空格和换行
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body_text = "\n".join(lines)
    return body_text

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
        text = fetch_webpage_text(url)
        summary = simple_summary(text)
        return clean_text(summary)
    except Exception as e:
        return f"无法获取摘要：{str(e)}"
