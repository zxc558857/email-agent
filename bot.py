import json
import os
import time
from datetime import datetime
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


def format_recent_emails(emails, limit=5):
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
{format_recent_emails(emails)}

自動整理僅使用規則，不使用 OpenAI API。
若需要 AI 深度摘要，請輸入「整理」或 /summary。
"""


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
    send_telegram_message("""
🤖 AI 郵件管家指令

📬 整理郵件：
整理
郵件整理
查看郵件
信箱
/summary

🏷️ Gmail 自動加標籤：
標籤
加標籤
分類
/label

📦 預覽可封存郵件：
封存
封存郵件
整理垃圾信
/archive

✅ 確認封存：
確認
確定
YES

❓ 查看指令：
幫助
指令
功能
/help
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
