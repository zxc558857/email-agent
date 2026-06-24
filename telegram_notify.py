import os

import requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram_message(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram 設定不完整，請確認 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID。")
        return {"ok": False, "error": "missing telegram config"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Telegram 訊息發送失敗：", e)
        return {"ok": False, "error": str(e)}
    except ValueError as e:
        print("Telegram 回傳格式錯誤：", e)
        return {"ok": False, "error": str(e)}
