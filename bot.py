import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from actions import get_archive_candidates, confirm_archive_candidates, auto_label_emails
from gmail_service import get_unread_emails
from telegram_notify import send_telegram_message

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
AUTO_HOURS = {8, 12, 17, 21}
AUTO_EMAIL_LIMIT = 20
STATE_FILE = Path("bot_state.json")
QUERY_LIMIT = 20
MESSAGE_SAFE_LIMIT = 3500

BANK_ALIASES = {
    "中國信託": ["中國信託", "中信"],
    "富邦": ["富邦", "台北富邦"],
    "國泰世華": ["國泰", "國泰世華"],
    "LINE Bank": ["line bank", "linebank", "LINE Bank"],
    "合作金庫": ["合作金庫", "合庫"],
    "永豐": ["永豐"],
    "玉山": ["玉山"],
    "元大": ["元大"],
    "台新": ["台新"],
}

TODAY_EMAIL_COMMANDS = {
    "今日郵件",
    "今天郵件",
    "今天的郵件",
    "今天有什麼郵件",
    "今天有什麼信",
}
RECENT_EMAIL_COMMANDS = {
    "最近郵件",
    "最近的郵件",
    "最近有什麼信",
}
IMPORTANT_EMAIL_COMMANDS = {
    "重要郵件",
    "最近重要郵件",
    "高重要郵件",
}
UPDATE_INDEX_COMMANDS = {
    "更新索引",
    "同步索引",
    "更新郵件索引",
}
SECURITY_COMMANDS = {
    "安全通知",
    "安全郵件",
    "帳號安全",
    "安全性快訊",
}


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("讀取排程狀態失敗，將使用空狀態：", e)
        return {}


def save_state(state):
    try:
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print("儲存排程狀態失敗：", e)


def is_gmail_token_error(error):
    text = str(error).lower()
    keywords = [
        "invalid_grant",
        "token has been expired",
        "token expired",
        "revoked",
        "refresh token",
        "invalid credentials",
    ]
    return any(keyword in text for keyword in keywords)


def send_error_message(action, error):
    if is_gmail_token_error(error):
        msg = (
            f"⚠️ {action}失敗：Gmail token 可能已失效。\n"
            "請刪除 token.json 後重新啟動 bot，依照瀏覽器流程重新授權 Gmail。"
        )
    else:
        msg = f"⚠️ {action}失敗：{error}"

    print(msg)
    send_telegram_message(msg)


def count_importance(emails):
    counts = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "archive": 0,
    }

    for mail in emails:
        importance = mail.get("importance", {})
        score = importance.get("score", 50)

        if score >= 80:
            counts["high"] += 1
        elif score >= 50:
            counts["medium"] += 1
        else:
            counts["low"] += 1

        if importance.get("can_archive") is True:
            counts["archive"] += 1

    return counts


def get_label_category(label_name):
    if label_name.startswith("AI/金融"):
        return "金融"
    if label_name == "AI/工作":
        return "工作"
    if label_name == "AI/學校":
        return "學校"
    if label_name == "AI/社群":
        return "社群"
    if label_name == "AI/購物":
        return "購物"
    if label_name == "AI/可封存":
        return "廣告"
    if label_name == "AI/AI資訊":
        return "AI資訊"
    if label_name == "AI/重要":
        return "重要"
    if label_name == "AI/一般":
        return "一般"
    return "其他"


def count_label_categories(labeled):
    categories = {
        "金融": 0,
        "工作": 0,
        "學校": 0,
        "社群": 0,
        "購物": 0,
        "廣告": 0,
        "AI資訊": 0,
        "重要": 0,
        "一般": 0,
        "其他": 0,
    }

    for item in labeled:
        category = get_label_category(item.get("label", ""))
        categories[category] += 1

    return categories


def format_unread_email_list(emails, limit=5):
    if not emails:
        return "目前沒有未讀郵件。"

    lines = []

    for i, mail in enumerate(emails[:limit], start=1):
        importance = mail.get("importance", {})
        level = importance.get("level", "未分類")
        score = importance.get("score", 0)
        subject = mail.get("subject") or "(無主旨)"
        lines.append(f"{i}. {subject}\n   重要度：{level}｜{score}分")

    return "\n".join(lines)


def build_rule_summary_message(emails, labeled, now_taipei):
    importance_counts = count_importance(emails)
    category_counts = count_label_categories(labeled)
    category_lines = "\n".join(
        f"{name}：{count}"
        for name, count in category_counts.items()
        if count > 0
    )

    if not category_lines:
        category_lines = "目前沒有可統計的分類。"

    return f"""
📬 郵件規則整理完成

時間：{now_taipei.strftime('%Y-%m-%d %H:%M')}

未讀郵件：{len(emails)} 封
已加 Gmail 標籤：{len(labeled)} 封

重要度統計：
🔴 高重要：{importance_counts['high']}
🟡 中重要：{importance_counts['medium']}
⚪ 低重要：{importance_counts['low']}
📦 可封存：{importance_counts['archive']}

分類統計：
{category_lines}

最近郵件：
{format_unread_email_list(emails)}

自動整理僅使用規則，不使用 OpenAI API。
若需要 AI 深度摘要，請輸入「整理」或 /summary。
"""


def normalize_query_text(text):
    return re.sub(r"\s+", "", (text or "").strip().lower())


def normalize_bank_name(text):
    normalized_text = normalize_query_text(text)
    for bank_name, aliases in BANK_ALIASES.items():
        for alias in aliases:
            if normalize_query_text(alias) in normalized_text:
                return bank_name
    return None


def get_current_month_range(now=None):
    now = now or datetime.now(TAIPEI_TZ)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return month_start, now


def get_today_range(now=None):
    now = now or datetime.now(TAIPEI_TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, now


def is_email_index_available():
    from email_index import DEFAULT_DB_PATH

    return DEFAULT_DB_PATH.exists()


def send_long_message(message):
    text = (message or "").strip()
    if not text:
        return

    chunks = []
    current = ""

    for line in text.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= MESSAGE_SAFE_LIMIT:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = line

        while len(current) > MESSAGE_SAFE_LIMIT:
            chunks.append(current[:MESSAGE_SAFE_LIMIT])
            current = current[MESSAGE_SAFE_LIMIT:]

    if current:
        chunks.append(current)

    for chunk in chunks:
        send_telegram_message(chunk)


def send_index_missing_message():
    send_long_message(
        """
⚠️ 尚未建立郵件索引。

請先輸入：
更新索引

如果需要建立歷史資料，可在電腦執行：
python email_index.py --sync --days 90
"""
    )


def format_email_datetime(mail, today_only=False):
    value = mail.get("date") or mail.get("internal_date")
    if value is None:
        return "--"

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value / 1000, tz=ZoneInfo("UTC"))
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return str(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    taipei_dt = dt.astimezone(TAIPEI_TZ)
    return taipei_dt.strftime("%H:%M" if today_only else "%m/%d %H:%M")


def format_email_date(mail):
    return format_email_datetime(mail).split(" ")[0]


def clean_sender(mail):
    sender = mail.get("sender") or mail.get("from") or ""
    name, email = parseaddr(sender)
    return name or email or sender or "(未知寄件者)"


def clean_subject(mail):
    return mail.get("subject") or "(無主旨)"


def category_name(mail):
    label = mail.get("category_label") or ""
    if mail.get("bank_name") or label.startswith("AI/金融"):
        return "金融"
    if mail.get("security_type") or label.startswith("AI/安全"):
        return "安全"
    if label == "AI/工作":
        return "工作"
    if label == "AI/學校":
        return "學校"
    return "其他"


def hidden_count(emails, limit=QUERY_LIMIT):
    return max(0, len(emails) - min(len(emails), limit))


def format_today_emails(emails, limit=QUERY_LIMIT):
    counts = Counter(category_name(mail) for mail in emails)
    high_count = sum(1 for mail in emails if (mail.get("importance_score") or 0) >= 80)
    shown = emails[:limit]

    lines = [
        "📬 今日郵件",
        "",
        f"今天共 {len(emails)} 封",
        "",
        f"🔴 高重要：{high_count}",
        f"🏦 金融：{counts['金融']}",
        f"🔐 安全：{counts['安全']}",
        f"💼 工作：{counts['工作']}",
        f"🎓 學校：{counts['學校']}",
        f"📨 其他：{counts['其他']}",
        "",
    ]

    if not shown:
        lines.append("目前沒有找到今天的郵件。")
        return "\n".join(lines)

    lines.append("最近郵件：")
    for i, mail in enumerate(shown, start=1):
        lines.extend(
            [
                f"{i}. {format_email_datetime(mail, today_only=True)}｜{clean_sender(mail)}",
                f"   {clean_subject(mail)}",
                "",
            ]
        )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def format_recent_index_emails(emails, limit=QUERY_LIMIT):
    shown = emails[:limit]
    lines = ["📬 最近郵件", ""]

    if not shown:
        lines.append("目前索引中沒有找到郵件。")
        return "\n".join(lines)

    for i, mail in enumerate(shown, start=1):
        lines.extend(
            [
                f"{i}. {format_email_datetime(mail)}",
                f"   {clean_sender(mail)}",
                f"   {clean_subject(mail)}",
                "",
            ]
        )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def format_important_emails(emails, limit=QUERY_LIMIT):
    shown = emails[:limit]
    lines = ["🔴 最近重要郵件", ""]

    if not shown:
        lines.append("目前索引中沒有找到重要郵件。")
        return "\n".join(lines)

    for i, mail in enumerate(shown, start=1):
        score = mail.get("importance_score") or 0
        lines.extend(
            [
                f"{i}. {score}分｜{clean_sender(mail)}",
                f"   {clean_subject(mail)}",
                "",
            ]
        )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def bank_title(bank_name):
    if not bank_name:
        return "銀行"
    if "Bank" in bank_name or bank_name.endswith("銀行"):
        return bank_name
    return f"{bank_name}銀行"


def format_bank_statements(emails, bank_name=None, current_month=False, limit=QUERY_LIMIT):
    shown = emails[:limit]
    if bank_name:
        title = f"🏦 {bank_title(bank_name)}{'本月' if current_month else ''}帳單"
    else:
        title = "🏦 本月銀行帳單" if current_month else "🏦 最近銀行帳單"

    lines = [title, ""]

    if not shown:
        lines.append("目前索引中沒有找到符合條件的帳單。")
        return "\n".join(lines)

    grouped = defaultdict(list)
    for mail in shown:
        grouped[mail.get("bank_name") or "其他"].append(mail)

    for group_name, rows in grouped.items():
        lines.append(f"【{group_name}】")
        for mail in rows:
            lines.extend(
                [
                    f"• {format_email_date(mail)}",
                    f"  {clean_subject(mail)}",
                    "",
                ]
            )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def is_abnormal_login(mail):
    subject = clean_subject(mail).lower()
    return any(keyword in subject for keyword in ["失敗", "異常", "unknown", "failed"])


def format_login_records(emails, bank_name=None, bank_only=False, limit=QUERY_LIMIT):
    shown = emails[:limit]
    if bank_name:
        title = f"🔐 {bank_title(bank_name)}登入紀錄"
    elif bank_only:
        title = "🔐 最近銀行登入紀錄"
    else:
        title = "🔐 最近登入紀錄"

    lines = [title, ""]

    if not shown:
        lines.append("目前索引中沒有找到登入紀錄。")
        return "\n".join(lines)

    normal = [mail for mail in shown if not is_abnormal_login(mail)]
    abnormal = [mail for mail in shown if is_abnormal_login(mail)]

    grouped = defaultdict(list)
    for mail in normal:
        grouped[mail.get("bank_name") or mail.get("security_type") or "一般"].append(mail)

    for group_name, rows in grouped.items():
        lines.append(f"【{group_name}】")
        for mail in rows:
            lines.extend(
                [
                    f"• {format_email_datetime(mail)}",
                    f"  {clean_subject(mail)}",
                    "",
                ]
            )

    if abnormal:
        lines.append("⚠️ 失敗／異常：")
        for mail in abnormal:
            lines.extend(
                [
                    f"• {format_email_datetime(mail)}",
                    f"  {clean_subject(mail)}",
                    "",
                ]
            )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def format_security_emails(emails, limit=QUERY_LIMIT):
    shown = emails[:limit]
    lines = ["🔐 最近安全通知", ""]

    if not shown:
        lines.append("目前沒有找到安全通知。")
        return "\n".join(lines)

    grouped = defaultdict(list)
    for mail in shown:
        grouped[mail.get("security_type") or "一般"].append(mail)

    for group_name, rows in grouped.items():
        lines.append(f"【{group_name}】")
        for mail in rows:
            lines.extend(
                [
                    f"• {format_email_date(mail)}",
                    f"  {clean_subject(mail)}",
                    "",
                ]
            )

    hidden = hidden_count(emails, limit)
    if hidden:
        lines.append(f"另外還有 {hidden} 封未顯示。")

    return "\n".join(lines).strip()


def build_sync_success_message(stats):
    return f"""
✅ 郵件索引更新完成

讀取：{stats.get('fetched', 0)}
新增：{stats.get('inserted', 0)}
更新：{stats.get('updated', 0)}
錯誤：{stats.get('errors', 0)}
"""


def build_sync_error_message(error):
    if is_gmail_token_error(error):
        detail = "Gmail token 可能已失效。"
    else:
        detail = "請稍後再試。"
    return f"⚠️ 郵件索引更新失敗：\n{detail}"


def detect_query(text):
    raw_text = (text or "").strip()
    normalized = normalize_query_text(raw_text)
    bank_name = normalize_bank_name(raw_text)

    if raw_text in UPDATE_INDEX_COMMANDS:
        return {"type": "update_index"}

    if raw_text in SECURITY_COMMANDS or "安全通知" in raw_text or "安全性快訊" in raw_text:
        return {"type": "security"}

    if raw_text in TODAY_EMAIL_COMMANDS or (
        ("今天" in raw_text or "今日" in raw_text)
        and ("郵件" in raw_text or "信" in raw_text)
    ):
        return {"type": "today"}

    if raw_text in IMPORTANT_EMAIL_COMMANDS or (
        "重要" in raw_text and ("郵件" in raw_text or "信" in raw_text)
    ):
        return {"type": "important"}

    if raw_text in RECENT_EMAIL_COMMANDS or (
        "最近" in raw_text
        and ("郵件" in raw_text or "信" in raw_text)
        and "重要" not in raw_text
    ):
        return {"type": "recent"}

    if "登入" in raw_text:
        bank_only = bank_name is not None or "銀行" in raw_text
        return {
            "type": "login",
            "bank_name": bank_name,
            "bank_only": bank_only,
        }

    is_statement = (
        "帳單" in raw_text
        or "對帳單" in raw_text
        or normalized in {"銀行帳單", "銀行對帳單", "帳單", "對帳單"}
    )
    if is_statement:
        current_month = "本月" in raw_text or "這個月" in raw_text
        return {
            "type": "bank_statement",
            "bank_name": bank_name,
            "current_month": current_month,
        }

    return None


def handle_query_command(query):
    if query["type"] == "update_index":
        handle_update_index_command()
        return True

    if not is_email_index_available():
        send_index_missing_message()
        return True

    from email_index import (
        get_bank_statements,
        get_emails,
        get_important_emails,
        get_login_records,
        get_recent_emails,
        get_security_emails,
    )

    try:
        if query["type"] == "today":
            date_from, date_to = get_today_range()
            emails = get_emails(date_from=date_from, date_to=date_to, limit=None)
            send_long_message(format_today_emails(emails))
        elif query["type"] == "recent":
            emails = get_recent_emails(limit=QUERY_LIMIT + 1, days=90)
            send_long_message(format_recent_index_emails(emails))
        elif query["type"] == "important":
            emails = get_important_emails(limit=QUERY_LIMIT + 1)
            send_long_message(format_important_emails(emails))
        elif query["type"] == "bank_statement":
            date_from = date_to = None
            if query.get("current_month"):
                date_from, date_to = get_current_month_range()
            emails = get_bank_statements(
                bank_name=query.get("bank_name"),
                date_from=date_from,
                date_to=date_to,
                limit=QUERY_LIMIT + 1,
            )
            send_long_message(
                format_bank_statements(
                    emails,
                    bank_name=query.get("bank_name"),
                    current_month=query.get("current_month", False),
                )
            )
        elif query["type"] == "login":
            emails = get_login_records(
                bank_name=query.get("bank_name"),
                bank_only=query.get("bank_only", False),
                limit=QUERY_LIMIT + 1,
            )
            send_long_message(
                format_login_records(
                    emails,
                    bank_name=query.get("bank_name"),
                    bank_only=query.get("bank_only", False),
                )
            )
        elif query["type"] == "security":
            emails = get_security_emails(limit=QUERY_LIMIT + 1)
            send_long_message(format_security_emails(emails))
        else:
            return False
    except Exception as e:
        print("郵件索引查詢失敗：", e)
        send_long_message("⚠️ 郵件索引查詢失敗，請稍後再試。")

    return True


def handle_update_index_command():
    send_long_message("🔄 正在更新最近 7 天郵件索引...")

    try:
        from email_index import sync_email_index

        stats = sync_email_index(days=7, progress=False)
    except Exception as e:
        print("郵件索引更新失敗：", e)
        send_long_message(build_sync_error_message(e))
        return

    send_long_message(build_sync_success_message(stats))


def run_summary(show_loading=False):
    if show_loading:
        send_telegram_message("📬 正在整理 Gmail，請稍等...")

    emails = get_unread_emails(limit=10)

    from ai_summary import summarize_emails

    summary = summarize_emails(emails)

    now_taipei = datetime.now(TAIPEI_TZ)

    message = f"""
📬 AI 郵件管家

時間：{now_taipei.strftime('%Y-%m-%d %H:%M')}

{summary}

自動整理時間：
08:00
12:00
17:00
21:00

目前版本：支援中文指令、/summary、/archive、/label 與自動整理。
"""

    send_telegram_message(message)


def run_rule_summary():
    emails = get_unread_emails(limit=AUTO_EMAIL_LIMIT)
    labeled = auto_label_emails() if emails else []

    now_taipei = datetime.now(TAIPEI_TZ)
    message = build_rule_summary_message(emails, labeled, now_taipei)

    send_telegram_message(message)


def get_updates(offset=None):
    if not TOKEN:
        print("Telegram token 未設定，無法取得更新。")
        return {"ok": False, "result": []}

    try:
        params = {"timeout": 30}

        if offset is not None:
            params["offset"] = offset

        response = requests.get(
            f"{BASE_URL}/getUpdates",
            params=params,
            timeout=60,
        )
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print("Telegram 連線失敗：", e)
        return {"ok": False, "result": []}
    except ValueError as e:
        print("Telegram 回傳格式錯誤：", e)
        return {"ok": False, "result": []}


def show_help():
    send_long_message("""
🤖 AI 郵件管家

📬 郵件查詢
今日郵件
最近郵件
重要郵件

🏦 銀行帳單
銀行帳單
本月帳單
富邦帳單
中國信託帳單

🔐 登入紀錄
登入紀錄
銀行登入
富邦登入
中國信託登入

🛡️ 安全
安全通知

🔄 索引
更新索引

🤖 AI 深度整理
整理
郵件整理
/summary

🏷️ Gmail 分類
分類
/label

📦 封存
封存
/archive

✅ 確認封存
確認
YES
""")


def handle_summary_command():
    try:
        run_summary(show_loading=True)
    except Exception as e:
        print("手動整理失敗：", e)
        send_error_message("郵件整理", e)


def handle_archive_command():
    try:
        candidates = get_archive_candidates()
    except Exception as e:
        print("封存預覽失敗：", e)
        send_error_message("封存預覽", e)
        return

    if not candidates:
        send_telegram_message("目前沒有符合封存條件的低風險郵件。")
        return

    msg = "📦 以下郵件符合封存條件：\n\n"

    for i, mail in enumerate(candidates, start=1):
        importance = mail.get("importance", {})
        msg += f"{i}. {mail.get('subject')}\n"
        msg += f"   重要度：{importance.get('level')}｜{importance.get('score')}分\n\n"

    msg += "若確認封存，請輸入：\n確認"

    send_telegram_message(msg)


def handle_label_command():
    try:
        labeled = auto_label_emails()
    except Exception as e:
        print("自動標籤失敗：", e)
        send_error_message("自動標籤", e)
        return

    if not labeled:
        send_telegram_message("目前沒有可加標籤的郵件。")
        return

    msg = "🏷️ 已完成 Gmail 自動加標籤：\n\n"

    for i, item in enumerate(labeled, start=1):
        msg += f"{i}. {item['subject']}\n"
        msg += f"   → {item['label']}\n\n"

    send_telegram_message(msg)


def handle_confirm_command():
    try:
        archived = confirm_archive_candidates()
    except Exception as e:
        print("確認封存失敗：", e)
        send_error_message("確認封存", e)
        return

    if not archived:
        send_telegram_message("沒有可封存的郵件。")
        return

    msg = "✅ 已完成封存：\n\n"

    for i, mail in enumerate(archived, start=1):
        msg += f"{i}. {mail.get('subject')}\n"

    send_telegram_message(msg)


def handle_message(text):
    raw_text = text.strip()
    command = raw_text.lower()

    summary_commands = [
        "/summary",
        "整理",
        "整理郵件",
        "郵件整理",
        "查看郵件",
        "看郵件",
        "信箱",
        "gmail",
        "幫我整理郵件",
        "幫我看信箱",
    ]

    archive_commands = [
        "/archive",
        "封存",
        "封存郵件",
        "整理垃圾信",
        "封存垃圾信",
        "清垃圾信",
        "清理郵件",
        "清理信箱",
    ]

    label_commands = [
        "/label",
        "標籤",
        "加標籤",
        "分類",
        "郵件分類",
        "幫我分類",
        "自動分類",
    ]

    confirm_commands = [
        "yes",
        "y",
        "確認",
        "確定",
        "封存確認",
        "確認封存",
    ]

    help_commands = [
        "/start",
        "/help",
        "幫助",
        "指令",
        "功能",
        "怎麼用",
        "使用說明",
    ]

    query = detect_query(raw_text)
    if query and handle_query_command(query):
        return

    if command in summary_commands:
        handle_summary_command()
    elif command in archive_commands:
        handle_archive_command()
    elif command in label_commands:
        handle_label_command()
    elif command in confirm_commands:
        handle_confirm_command()
    elif command in help_commands:
        show_help()
    else:
        send_telegram_message("看不懂指令，可以輸入「幫助」查看功能。")


def should_run_auto_summary(now, state):
    if now.hour not in AUTO_HOURS or now.minute > 1:
        return False, None

    run_key = now.strftime("%Y-%m-%d-%H")

    if state.get("last_auto_run_key") == run_key:
        return False, run_key

    return True, run_key


def run_auto_summary(run_key, state):
    state["last_auto_run_key"] = run_key
    state["last_auto_run_started_at"] = datetime.now(TAIPEI_TZ).isoformat()
    state["last_auto_run_status"] = "running"
    save_state(state)

    print(f"自動整理啟動：{run_key}")

    try:
        run_rule_summary()
        state["last_auto_run_status"] = "success"
        state.pop("last_auto_run_error", None)
    except Exception as e:
        print("自動整理失敗：", e)
        state["last_auto_run_status"] = "failed"
        state["last_auto_run_error"] = str(e)
        send_error_message("自動整理", e)
    finally:
        state["last_auto_run_finished_at"] = datetime.now(TAIPEI_TZ).isoformat()
        save_state(state)


def main():
    print("AI Email Agent Bot started...")

    offset = None
    state = load_state()

    latest = get_updates()

    if latest.get("ok") and latest.get("result"):
        offset = latest["result"][-1]["update_id"] + 1

    while True:
        try:
            now = datetime.now(TAIPEI_TZ)
            should_run, run_key = should_run_auto_summary(now, state)

            if should_run:
                run_auto_summary(run_key, state)

            updates = get_updates(offset)

            if updates.get("ok"):
                for update in updates.get("result", []):
                    offset = update["update_id"] + 1

                    message = update.get("message", {})
                    text = message.get("text", "")

                    if text:
                        print("收到指令：", text)
                        handle_message(text)

        except Exception as e:
            print("主迴圈錯誤：", e)

        time.sleep(10)


if __name__ == "__main__":
    main()
