import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bank_aliases import BANK_ALIASES, normalize_bank_name, normalize_query_text


TAIPEI_TZ = ZoneInfo("Asia/Taipei")
DEFAULT_LIMIT = 20
DEFAULT_RECENT_DAYS = 90

PROTECTED_COMMANDS = {
    "/summary",
    "/label",
    "/archive",
    "/help",
    "/start",
    "整理",
    "整理郵件",
    "郵件整理",
    "分類",
    "封存",
    "確認",
    "更新索引",
}


@dataclass
class ParsedQuery:
    matched: bool
    intent: str | None = None
    bank: str | None = None
    keyword: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    status: str | None = None
    category: str | None = None
    min_importance: int | None = None
    bank_only: bool = False
    limit: int = DEFAULT_LIMIT
    confidence: float = 0.0
    reason: str = ""
    date_label: str | None = None


def parse_query(text, now=None):
    raw_text = (text or "").strip()
    if not raw_text:
        return _no_match("empty")

    normalized = normalize_query_text(raw_text)
    protected = {normalize_query_text(command) for command in PROTECTED_COMMANDS}
    if normalized in protected:
        return _no_match("protected_command")

    now = _taipei_now(now)
    date_from, date_to, date_label = parse_date_range(raw_text, now)
    bank = normalize_bank_name(raw_text)

    if _is_action_required(raw_text):
        return _matched(
            "action_required",
            date_from,
            date_to,
            date_label,
            reason="action_required_keywords",
        )

    if _is_reply_required(raw_text):
        return _matched(
            "reply_required",
            date_from,
            date_to,
            date_label,
            reason="reply_required_keywords",
        )

    if _is_bank_statement_query(raw_text):
        return _matched(
            "bank_statements",
            date_from,
            date_to,
            date_label,
            bank=bank,
            reason="bank_statement_keywords",
        )

    if _is_login_query(raw_text):
        return _matched(
            "login_records",
            date_from,
            date_to,
            date_label,
            bank=bank,
            status=_login_status(raw_text),
            bank_only=bool(bank or "銀行" in raw_text),
            reason="login_keywords",
        )

    if _is_security_query(raw_text):
        keyword = _security_keyword(raw_text)
        return _matched(
            "security_emails",
            date_from,
            date_to,
            date_label,
            keyword=keyword,
            reason="security_keywords",
        )

    if _is_important_query(raw_text):
        intent = "today_emails" if _is_today_query(raw_text) else "important_emails"
        return _matched(
            intent,
            date_from,
            date_to,
            date_label,
            min_importance=80,
            reason="important_keywords",
        )

    if _is_work_query(raw_text):
        return _matched(
            "work_emails",
            date_from,
            date_to,
            date_label,
            category="AI/工作%",
            reason="work_keywords",
        )

    if _is_school_query(raw_text):
        return _matched(
            "school_emails",
            date_from,
            date_to,
            date_label,
            category="AI/學校%",
            reason="school_keywords",
        )

    sender = _sender_search_term(raw_text)
    if sender:
        return _matched(
            "sender_search",
            date_from,
            date_to,
            date_label,
            keyword=sender,
            reason="sender_search",
        )

    keyword = _keyword_search_term(raw_text)
    if keyword:
        return _matched(
            "keyword_search",
            date_from,
            date_to,
            date_label,
            keyword=keyword,
            reason="keyword_search",
        )

    if _is_today_query(raw_text):
        return _matched(
            "today_emails",
            date_from,
            date_to,
            date_label,
            reason="today_mail_keywords",
        )

    if _is_general_mail_query(raw_text):
        return _matched(
            "recent_emails",
            date_from,
            date_to,
            date_label,
            reason="general_mail_keywords",
        )

    return _no_match("no_reliable_rule")


def parse_date_range(text, now=None):
    raw_text = text or ""
    normalized = normalize_query_text(raw_text)
    now = _taipei_now(now)

    if "今天" in raw_text or "今日" in raw_text:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now, "今天"

    if "昨天" in raw_text or "昨日" in raw_text:
        start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end, "昨天"

    if _contains_any(normalized, ["上星期", "上週"]):
        this_week_start = _week_start(now)
        return this_week_start - timedelta(days=7), this_week_start, "上週"

    if _contains_any(normalized, ["這個星期", "這星期", "這週", "本週"]):
        return _week_start(now), now, "本週"

    if _contains_any(normalized, ["上個月", "上月"]):
        this_month = _month_start(now)
        return _shift_month(this_month, -1), this_month, "上月"

    if _contains_any(normalized, ["這個月", "本月"]):
        return _month_start(now), now, "本月"

    months = _recent_months(normalized)
    if months:
        return _shift_month(now, -months), now, f"最近{months}個月"

    days = _recent_days(normalized)
    if days:
        return now - timedelta(days=days), now, f"最近{days}天"

    if "最近" in raw_text or "近" in raw_text:
        return now - timedelta(days=DEFAULT_RECENT_DAYS), now, "最近"

    return None, None, None


def _matched(
    intent,
    date_from,
    date_to,
    date_label,
    bank=None,
    keyword=None,
    status=None,
    category=None,
    min_importance=None,
    bank_only=False,
    reason="",
):
    return ParsedQuery(
        matched=True,
        intent=intent,
        bank=bank,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        status=status,
        category=category,
        min_importance=min_importance,
        bank_only=bank_only,
        confidence=0.9,
        reason=reason,
        date_label=date_label,
    )


def _no_match(reason):
    return ParsedQuery(matched=False, confidence=0.0, reason=reason)


def _taipei_now(now=None):
    if now is None:
        return datetime.now(TAIPEI_TZ)
    if now.tzinfo is None:
        return now.replace(tzinfo=TAIPEI_TZ)
    return now.astimezone(TAIPEI_TZ)


def _week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(now):
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(value, delta):
    month = value.month - 1 + delta
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return value.replace(year=year, month=month, day=day)


def _days_in_month(year, month):
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=TAIPEI_TZ)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=TAIPEI_TZ)
    return (next_month - timedelta(days=1)).day


def _contains_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def _recent_days(normalized):
    match = re.search(r"(?:最近|近|這)(\d+)天", normalized)
    if match:
        return int(match.group(1))
    chinese_days = {"七": 7, "三十": 30}
    for word, value in chinese_days.items():
        if f"最近{word}天" in normalized or f"近{word}天" in normalized:
            return value
    return None


def _recent_months(normalized):
    match = re.search(r"(?:最近|近)(\d+)個月", normalized)
    if match:
        return int(match.group(1))
    chinese_months = {"三": 3}
    for word, value in chinese_months.items():
        if f"最近{word}個月" in normalized or f"近{word}個月" in normalized:
            return value
    return None


def _is_today_query(text):
    return ("今天" in text or "今日" in text) and _has_mail_word(text)


def _is_general_mail_query(text):
    if not _has_mail_word(text):
        return False
    return any(
        phrase in text
        for phrase in ["昨天", "昨日", "最近", "本週", "這週", "這星期", "這個星期", "本月", "這個月"]
    )


def _has_mail_word(text):
    return "郵件" in text or "信" in text


def _is_important_query(text):
    return "重要" in text and _has_mail_word(text)


def _is_bank_statement_query(text):
    return ("帳單" in text or "對帳單" in text) and (
        "銀行" in text or normalize_bank_name(text) is not None
    )


def _is_login_query(text):
    return "登入" in text and (
        "銀行" in text
        or "紀錄" in text
        or "記錄" in text
        or normalize_bank_name(text) is not None
        or "失敗" in text
        or "異常" in text
    )


def _login_status(text):
    lowered = text.lower()
    if "失敗" in text or "failed" in lowered:
        return "failure"
    if any(word in text for word in ["異常", "可疑", "不正常", "陌生登入"]):
        return "abnormal"
    if "成功" in text:
        return "success"
    return None


def _is_security_query(text):
    if "安全通知" in text or "安全性快訊" in text:
        return True
    if any(word in text for word in ["第三方授權", "密碼重置"]):
        return True
    return "通知" in text and any(word in text for word in ["Passkey", "passkey", "密碼", "驗證"])


def _security_keyword(text):
    for keyword in ["Passkey", "passkey", "第三方授權", "密碼", "登入", "驗證"]:
        if keyword in text:
            return "Passkey" if keyword.lower() == "passkey" else keyword

    before_security = re.split(r"安全通知|安全性快訊", text, maxsplit=1)[0]
    return _clean_extracted_term(before_security)


def _is_reply_required(text):
    return any(phrase in text for phrase in ["需要我回覆", "需要回覆", "要回覆", "待回覆"])


def _is_action_required(text):
    return any(phrase in text for phrase in ["需要我處理", "需要處理", "要處理"])


def _is_work_query(text):
    return "工作" in text and _has_mail_word(text)


def _is_school_query(text):
    return "學校" in text and _has_mail_word(text)


def _keyword_search_term(text):
    quoted = _quoted_term(text)
    if quoted and any(word in text for word in ["找", "搜尋", "包含", "相關"]):
        return quoted

    match = re.search(r"(?:找有|找包含|搜尋|找)(.+?)(?:的)?(?:郵件|信|相關郵件)?[？?]?$", text)
    if not match:
        return None

    term = _clean_extracted_term(match.group(1))
    if not term:
        return None
    if "最近" in text and ("寄" in text or normalize_bank_name(term)):
        return None
    return term


def _sender_search_term(text):
    if any(word in text for word in ["找有", "找包含", "搜尋", "相關"]):
        return None
    if "寄" not in text and not re.search(r"(幫我)?找.+(?:郵件|信)", text):
        return None

    term = text
    term = _strip_date_words(term)
    replacements = [
        "幫我找",
        "請問",
        "想知道",
        "有寄什麼給我",
        "有寄什麼",
        "寄了什麼",
        "寄了哪些信",
        "寄了哪些郵件",
        "寄了哪些",
        "最近的信",
        "的郵件",
        "的信",
        "郵件",
        "信",
        "給我",
        "找",
        "有沒有",
        "有哪些",
        "有什麼",
        "嗎",
        "呢",
        "？",
        "?",
    ]
    for item in replacements:
        term = term.replace(item, "")
    return _clean_extracted_term(term)


def _quoted_term(text):
    match = re.search(r"[「『\"](.+?)[」』\"]", text)
    if match:
        return match.group(1).strip()
    return None


def _strip_date_words(text):
    patterns = [
        "最近三個月",
        "最近3個月",
        "近三個月",
        "近3個月",
        "最近30天",
        "最近 30 天",
        "近30天",
        "最近7天",
        "最近 7 天",
        "近7天",
        "這個星期",
        "這星期",
        "這個月",
        "本星期",
        "本週",
        "這週",
        "本月",
        "上星期",
        "上週",
        "上個月",
        "上月",
        "今天",
        "今日",
        "昨天",
        "昨日",
        "最近",
    ]
    for pattern in patterns:
        text = text.replace(pattern, "")
    return text


def _clean_extracted_term(term):
    term = _strip_date_words(term or "")
    term = re.sub(r"[「」『』\"'：:，,。？?\s]", "", term)
    for filler in ["幫我", "請問", "想知道", "有沒有", "有哪些", "有什麼", "包含", "相關", "通知"]:
        term = term.replace(filler, "")
    if not term:
        return None

    bank = normalize_bank_name(term)
    if bank and normalize_query_text(term) in {
        normalize_query_text(alias)
        for aliases in BANK_ALIASES.values()
        for alias in aliases
    }:
        return bank
    return term.strip()
