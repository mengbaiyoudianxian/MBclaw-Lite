import re
from collections import Counter
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.models.message import Message
from app.models.keyword import Keyword

STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "哪",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each", "every",
    "all", "any", "few", "more", "most", "other", "some", "such", "no",
    "only", "own", "same", "than", "too", "very", "just", "because",
    "about", "up", "out", "if", "then", "now", "here", "there", "when",
    "where", "why", "how", "which", "who", "whom", "this", "that",
    "these", "those", "it", "its", "ok", "okay", "yeah", "yes",
}


def _tokenize(text: str) -> list[str]:
    try:
        import jieba
        words = jieba.lcut(text)
    except Exception:
        words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_-]{2,}", text)
    return [w.strip().lower() for w in words if len(w.strip()) >= 2 and w.strip() not in STOP_WORDS]


def extract_keywords(db: DBSession, session: Session) -> list[Keyword]:
    messages = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    full_text = " ".join(m.content for m in messages)

    words = _tokenize(full_text)
    if not words:
        return []

    counter = Counter(words)
    top_keywords = counter.most_common(15)

    db.query(Keyword).filter(Keyword.session_id == session.id).delete()

    result = []
    for kw, count in top_keywords:
        weight = min(count / max(1, len(words)) * 100, 10.0)
        keyword = Keyword(
            session_id=session.id,
            project_id=session.project_id,
            keyword=kw,
            weight=round(weight, 2),
        )
        db.add(keyword)
        result.append(keyword)

    db.flush()
    return result
