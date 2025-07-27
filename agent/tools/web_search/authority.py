from urllib.parse import urlparse

# 权威性参考表（可扩展）
AUTHORITY_SCORES = {
    # 政府与官方机构
    "gov.cn": 9.5, "government.uk": 9.5, "usa.gov": 9.5,
    "europa.eu": 9.5, "who.int": 9.8, "un.org": 9.7,
    "weather.com.cn": 9.4,

    # 权威媒体
    "xinhuanet.com": 9.0, "people.com.cn": 9.0, "cctv.com": 9.0,
    "bbc.com": 9.2, "nytimes.com": 9.2, "reuters.com": 9.3,
    "wsj.com": 9.1, "ap.org": 9.4, "bloomberg.com": 9.1,

    # 学术机构
    "edu.cn": 9.0, "harvard.edu": 9.6, "mit.edu": 9.6,
    "nature.com": 9.7, "sciencemag.org": 9.7, "thelancet.com": 9.6,

    # 科技公司
    "microsoft.com": 8.5, "google.com": 8.7, "apple.com": 8.5,
    "oracle.com": 8.3, "ibm.com": 8.4,

    # 常见但权威性较低
    "wikipedia.org": 7.5, "github.com": 7.8, "medium.com": 6.5,
    "blogspot.com": 5.5, "wordpress.com": 5.5
}

def calculate_authority_score(url):
    """从URL提取域名并获取权威性评分"""
    try:
        domain = urlparse(url).netloc
        # 移除www前缀
        if domain.startswith("www."):
            domain = domain[4:]

        # 尝试匹配完整域名
        if domain in AUTHORITY_SCORES:
            return AUTHORITY_SCORES[domain]

        # 尝试匹配二级域名
        domain_parts = domain.split('.')
        if len(domain_parts) > 2:
            base_domain = '.'.join(domain_parts[-2:])
            return AUTHORITY_SCORES.get(base_domain, 5.0)  # 默认5.0

        return 5.0  # 默认分数
    except:
        return 5.0  # 异常情况默认分数
