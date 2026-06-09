from gmail_service import get_unread_emails
from ai_summary import summarize_emails
from telegram_notify import send_telegram_message

def main():
    emails = get_unread_emails(limit=10)

    summary = summarize_emails(emails)

    message = f"""
📬 AI 郵件管家測試版

{summary}

目前版本：只整理摘要，尚未自動刪除或封存。
"""

    send_telegram_message(message)

if __name__ == "__main__":
    main()