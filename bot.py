import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from actions import get_archive_candidates, confirm_archive_candidates

from gmail_service import get_unread_emails
from ai_summary import summarize_emails
from telegram_notify import send_telegram_message

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

def run_summary():

    send_telegram_message("📬 正在整理 Gmail，請稍等...")

    emails = get_unread_emails(limit=10)

    summary = summarize_emails(emails)

    message = f"""
📬 AI 郵件管家

時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}

{summary}

自動整理時間：
08:00
12:00
17:00
21:00

目前版本：支援 /summary 與自動整理。
"""

    send_telegram_message(message)

def get_updates(offset=None):
    params = {
        "timeout": 30
    }

    if offset:
        params["offset"] = offset

    response = requests.get(
        f"{BASE_URL}/getUpdates",
        params=params
    )

    return response.json()


def handle_message(text):
    if text == "/summary":
        run_summary()

    elif text == "/archive":
        candidates = get_archive_candidates()

        if not candidates:
            send_telegram_message("目前沒有符合封存條件的低風險郵件。")
            return

        msg = "📦 以下郵件符合封存條件：\n\n"

        for i, mail in enumerate(candidates, start=1):
            importance = mail.get("importance", {})
            msg += f"{i}. {mail.get('subject')}\n"
            msg += f"   重要度：{importance.get('level')}｜{importance.get('score')}分\n\n"

        msg += "若確認封存，請輸入：\nYES"

        send_telegram_message(msg)

    elif text == "YES":
        archived = confirm_archive_candidates()

        if not archived:
            send_telegram_message("沒有可封存的郵件。")
            return

        msg = "✅ 已完成封存：\n\n"

        for i, mail in enumerate(archived, start=1):
            msg += f"{i}. {mail.get('subject')}\n"

        send_telegram_message(msg)

    elif text == "/start":
        send_telegram_message(
            "你好，我是 AI 郵件管家。\n\n可用指令：\n/summary 重新整理郵件\n/archive 預覽可封存郵件\nYES 確認封存"
        )

    else:
        send_telegram_message(
            "目前支援指令：\n/summary 重新整理 Gmail\n/archive 預覽可封存郵件\nYES 確認封存"
        )


def main():
    print("AI Email Agent Bot started...")

    offset = None
    last_auto_run_key = None

    auto_hours = [8, 12, 17, 21]

    while True:

        now = datetime.now()

        # 自動整理時段
        if now.hour in auto_hours and now.minute == 0:

            run_key = now.strftime("%Y-%m-%d-%H")

            if last_auto_run_key != run_key:

                print(f"自動整理啟動：{run_key}")

                run_summary()

                last_auto_run_key = run_key

        updates = get_updates(offset)

        if updates.get("ok"):
            for update in updates.get("result", []):

                offset = update["update_id"] + 1

                message = update.get("message", {})
                text = message.get("text", "")

                if text:
                    print("收到指令：", text)

                    handle_message(text)

        time.sleep(10)


if __name__ == "__main__":
    main()