import os
from collections import deque

class Node:
    def __init__(self):
        self.children = dict()
        self.fail = None
        self.output = set()

class AhoCorasickAutomaton:
    def __init__(self, words):
        self.root = Node()
        for word in words:
            self._insert(word)
        self._build_fail()

    def _insert(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = Node()
            node = node.children[char]
        node.output.add(word)

    def _build_fail(self):
        queue = deque()
        for child in self.root.children.values():
            child.fail = self.root
            queue.append(child)
        while queue:
            rnode = queue.popleft()
            for key, unode in rnode.children.items():
                queue.append(unode)
                fnode = rnode.fail
                while fnode and key not in fnode.children:
                    fnode = fnode.fail
                unode.fail = fnode.children[key] if fnode and key in fnode.children else self.root
                unode.output |= unode.fail.output

    def search(self, text):
        node = self.root
        found = set()
        for char in text:
            while node and char not in node.children:
                node = node.fail
            node = node.children[char] if node and char in node.children else self.root
            if node.output:
                found |= node.output
        return list(found)

def _load_sensitive_words():
    """
    合并多个敏感词库文件，支持 konsheng/Sensitive-lexicon 项目
    默认路径为 web_search/sensitive_lexicon/ 下的目标文件
    """
    base_dir = os.path.join(os.path.dirname(__file__), "Sensitive-lexicon", "Vocabulary")
    files = [
        "民生词库.txt",
        "色情词库.txt",
        "反动词库.txt",
        "其他词库.txt",
        "暴恐词库.txt"
    ]
    words = set()
    for fname in files:
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath, encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:
                    words.add(word)
    return list(words)

# 初始化自动机，只在模块初始化时构建一次
_sensitive_automaton = AhoCorasickAutomaton(_load_sensitive_words())

def filter_sensitive_results(results):
    """
    过滤掉含敏感内容的搜索结果
    :param results: [{'title': ..., 'snippet': ..., ...}, ...]
    :return: 过滤后的列表
    """
    filtered = []
    for item in results:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if _sensitive_automaton.search(title):
            continue
        if _sensitive_automaton.search(snippet):
            continue
        filtered.append(item)
    return filtered

import os
from urllib.parse import urlparse

def _load_blocked_rules():
    """
    加载 web_search/gfwlist/list.txt，返回规则集合（域名/主机/URL片段）
    """
    rules = set()
    fpath = os.path.join(os.path.dirname(__file__), "gfwlist", "list.txt")
    with open(fpath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("!") or line.startswith("!!") or line.startswith("!----"):
                continue
            # 去掉 abp/通配符前缀
            line = line.lstrip('|.')
            # 不处理 http/https 前缀，只关注主机/域名/路径
            if line:
                rules.add(line)
    return rules

_blocked_rules = _load_blocked_rules()

def _get_domain(url: str) -> str:
    """
    提取主域名（例如 youtube.com），忽略子域名
    """
    try:
        hostname = urlparse(url).hostname or ''
        # 截取最后两段（如 www.youtube.com -> youtube.com）
        parts = hostname.split('.')
        if len(parts) >= 2:
            domain = '.'.join(parts[-2:])
        else:
            domain = hostname
        return domain.lower()
    except Exception:
        return ''

def filter_blocked_domains(results):
    """
    过滤掉 url 在 list.txt 规则中的搜索结果
    :param results: [{'url': ..., ...}, ...]
    :return: 过滤后的列表
    """
    filtered = []
    for item in results:
        url = item.get("link", "")
        domain = _get_domain(url)
        if domain and domain in _blocked_rules:
            continue
        filtered.append(item)

    return filtered
