import jieba
import re

def calculate_relevance_score(item, query):
    # 中文分词
    def segment(text):
        return set(jieba.lcut(re.sub(r'[^\w\s]', '', text.lower())))

    query_words = segment(query)
    title_words = segment(item['title'])
    snippet_words = segment(item['snippet'])

    # 标题命中词数/总词数
    title_overlap = query_words & title_words
    snippet_overlap = query_words & snippet_words

    # 权重分配：标题7分，snippet 3分
    title_score = len(title_overlap) / len(query_words) * 6 if query_words else 0
    snippet_score = len(snippet_overlap) / len(query_words) * 4 if query_words else 0

    # 若标题或snippet包含query原短语，加2分（短语级别）
    phrase_bonus = 0
    if query in item['title']:
        phrase_bonus += 1
    if query in item['snippet']:
        phrase_bonus += 1

    # 负向惩罚（标题党）
    if title_score >= 6 and snippet_score < 1:
        snippet_score -= 1

    total = title_score + snippet_score + phrase_bonus
    return round(max(0, min(10, total)), 2)
