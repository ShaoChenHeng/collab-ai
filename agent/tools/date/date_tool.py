# 日期工具
from datetime import datetime
from langchain_core.tools import tool
from pydantic import BaseModel


class GetDateSchema(BaseModel):
    pass

@tool(args_schema=GetDateSchema)
def today_date() -> list:
    """
    必须调用此工具的情况：
    1. 用户问题包含'今天'、'当前日期'、'哪天'、'最新'、'最近'等时间相关词
    2. 需要基准时间处理'过去'或'未来'相关概念
    返回格式: YYYY年MM月DD日
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    return today

def parse_cn_date(date_str):
    # 假定输入格式为 "2025年08月17日"
    return datetime.strptime(date_str, "%Y年%m月%d日").date()

def date_diff_days(date1_str, date2_str):
    date1 = parse_cn_date(date1_str)
    date2 = parse_cn_date(date2_str)
    return abs((date1 - date2).days)

def date_diff_hint(diff_days):
    """
    根据日期差距生成用于LLM prompt的推荐语（拓展至半年、一年、三年、三年以上）。
    仅依赖diff_days，涵盖实时类、一般资讯、学术/教程/原理等常见类别。
    """
    if diff_days == 0:
        return "信息日期与当前日期完全一致，非常推荐选用（适用于实时类如天气、新闻、产品等）。"
    elif diff_days == 1:
        return "信息日期与当前日期仅相差1天，推荐选用，实时类问题高度相关。"
    elif 1 < diff_days <= 3:
        return "信息日期与当前日期相差3天以内，可作为参考，实时类问题相关性较强。"
    elif 3 < diff_days <= 7:
        return "信息日期与当前日期相差7天以内，内容可参考，但实时性可能略有下降。"
    elif 7 < diff_days <= 30:
        return "信息日期与当前日期相差30天以内，适合一般资讯、教程、学术等非强实时内容。"
    elif 30 < diff_days <= 183:
        return "信息日期与当前日期相差半年以内，适合非实时类内容，学术、教程、原理等均可选用。"
    elif 183 < diff_days <= 365:
        return "信息日期与当前日期相差一年以内，适合学术、原理、经验类内容，时效要求不高的问题可参考。"
    elif 365 < diff_days <= 1095:
        return "信息日期与当前日期相差三年以内，内容适合学术、历史、原理等领域，时效性要求低的问题可选用。"
    else:
        return "信息日期与当前日期相差三年以上，仅适合历史、学术、原理类内容，实时性强的问题不推荐。"
