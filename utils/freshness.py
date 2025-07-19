import datetime
import re
from dateutil.relativedelta import relativedelta

def extract_date_from_snippet(snippet):
    """从snippet中智能提取日期信息，只保留年月日"""
    # 提取snippet前100个字符（日期通常出现在开头）
    text = snippet[:100].lower()

    # 当前日期（只取日期部分）
    today = datetime.date.today()
    now = datetime.datetime.now()

    # 1. 处理相对时间格式
    relative_patterns = [
        (r'(\d+)\s*(minute|min)\s*ago', 'minutes'),
        (r'(\d+)\s*(hour|hr)\s*ago', 'hours'),
        (r'(\d+)\s*day(s)?\s*ago', 'days'),
        (r'(\d+)\s*week(s)?\s*ago', 'weeks'),
        (r'(\d+)\s*month(s)?\s*ago', 'months'),
        (r'(\d+)\s*year(s)?\s*ago', 'years'),
        (r'(\d+)\s*(分钟|小时|天|周|月|年)前', None)  # 中文相对时间
    ]

    for pattern, unit in relative_patterns:
        match = re.search(pattern, text)
        if match:
            num = int(match.group(1))
            # 中文处理
            if not unit:
                chinese_unit = match.group(2)
                unit_map = {
                    "分钟": "minutes", "小时": "hours", "天": "days",
                    "周": "weeks", "月": "months", "年": "years"
                }
                unit = unit_map.get(chinese_unit, "days")

            # 计算相对时间并只保留日期部分
            kwargs = {unit: num}
            result_date = now - relativedelta(**kwargs)
            return result_date.date()  # 只返回日期部分

    # 2. 处理中文日期格式
    chinese_patterns = [
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',  # 完整日期 2025年7月17日
        r'(\d{1,2})月(\d{1,2})日',          # 无年份日期 7月17日
        r'今天|今日',                        # 今天
        r'昨天|昨日',                        # 昨天
        r'前天'                             # 前天
    ]

    for pattern in chinese_patterns:
        match = re.search(pattern, text)
        if match:
            if "今天" in pattern or "今日" in pattern:
                return today  # 直接返回日期对象
            elif "昨天" in pattern or "昨日" in pattern:
                return today - datetime.timedelta(days=1)
            elif "前天" in pattern:
                return today - datetime.timedelta(days=2)
            elif len(match.groups()) == 3:  # 完整日期
                year, month, day = map(int, match.groups())
                return datetime.date(year, month, day)  # 创建日期对象
            elif len(match.groups()) == 2:  # 无年份日期
                month, day = map(int, match.groups())
                year = today.year
                if month > today.month:
                    year -= 1
                return datetime.date(year, month, day)  # 创建日期对象

    # 3. 处理英文日期格式
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10,
        'november': 11, 'december': 12
    }

    en_patterns = [
        r'(\w{3,9})\s*(\d{1,2}),?\s*(\d{4})',  # Jul 9, 2025
        r'(\d{1,2})\s*(\w{3,9})\s*(\d{4})',    # 9 Jul 2025
        r'(\d{4})-(\d{1,2})-(\d{1,2})',        # ISO格式 2025-07-09
        r'(\d{1,2})/(\d{1,2})/(\d{4})',        # 美式日期 7/9/2025
        r'(\w{3,9})\s*(\d{1,2})',              # 无年份日期 Jul 9
    ]

    for pattern in en_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:  # 完整日期
                try:
                    # 格式1: 月 日, 年
                    if groups[0].isalpha():
                        month = month_map.get(groups[0][:3].lower(), 1)
                        day = int(groups[1].strip(','))
                        year = int(groups[2])
                        return datetime.date(year, month, day)  # 创建日期对象
                    # 格式2: 日 月 年
                    elif groups[1].isalpha():
                        day = int(groups[0])
                        month = month_map.get(groups[1][:3].lower(), 1)
                        year = int(groups[2])
                        return datetime.date(year, month, day)  # 创建日期对象
                    # 数字格式
                    else:
                        year, month, day = map(int, groups)
                        # 处理美式日期 (月/日/年)
                        if pattern == r'(\d{1,2})/(\d{1,2})/(\d{4})':
                            month, day = day, month
                        return datetime.date(year, month, day)  # 创建日期对象
                except (ValueError, KeyError):
                    continue

            elif len(groups) == 2:  # 无年份日期
                try:
                    if groups[0].isalpha():  # 月 日
                        month = month_map.get(groups[0][:3].lower(), 1)
                        day = int(groups[1])
                    else:  # 日 月
                        day = int(groups[0])
                        month = month_map.get(groups[1][:3].lower(), 1)

                    year = today.year
                    # 如果月份大于当前月份，则是去年
                    if month > today.month:
                        year -= 1
                    return datetime.date(year, month, day)  # 创建日期对象
                except (ValueError, KeyError):
                    continue

    # 4. 处理数字相对时间（如1小时前）
    num_relative = re.search(r'(\d+)\s*(h|d|w|m|y)\s*前?', text)
    if num_relative:
        num = int(num_relative.group(1))
        unit = num_relative.group(2)
        unit_map = {'h': 'hours', 'd': 'days', 'w': 'weeks', 'm': 'months', 'y': 'years'}
        if unit in unit_map:
            kwargs = {unit_map[unit]: num}
            result_date = now - relativedelta(**kwargs)
            return result_date.date()  # 只返回日期部分

    # 5. 处理"今天"类表达（多种语言）
    today_expr = re.search(r'(today|now|just now|今天|今日|当前)', text)
    if today_expr:
        return today  # 直接返回日期对象

    # 没有找到日期信息
    return None

def calculate_freshness_score(date_obj):
    """计算信息的新鲜度评分"""
    if not date_obj:
        return 2.0 # 如果没有日期对象，返回最低分

    today = datetime.date.today()
    delta_days = (today - date_obj).days

    if delta_days < 1:
        return 10.0  # 今天
    elif delta_days < 3:
        return 9.0  # 三天内
    elif delta_days < 7:
        return 8.0  # 一周内
    elif delta_days < 15:
        return 7.0  # 两周内
    elif delta_days < 30:
        return 6.0  # 一个月内
    elif delta_days < 90:
        return 6.0  # 三个月内
    elif delta_days < 180:
        return 5.0  # 六个月内
    elif delta_days < 365:
        return 4.0  # 一年内
    elif delta_days < 365 * 3:
        return 3.0  # 三年内
    else:
        return 2.0  # 三年以上
