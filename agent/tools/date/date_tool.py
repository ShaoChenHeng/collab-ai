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
