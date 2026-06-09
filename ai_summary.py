import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_emails(emails):
    if not emails:
        return "📭 目前沒有未讀郵件。"

    email_text = ""

    for i, mail in enumerate(emails, start=1):
        importance = mail.get("importance", {})

        email_text += f"""
第 {i} 封
重要度：{importance.get('level')}｜{importance.get('score')}分
可封存：{importance.get('can_archive')}
寄件者：{mail['from']}
主旨：{mail['subject']}
摘要：{mail['snippet']}
"""

    prompt = f"""
你是一個個人郵件整理助理。

請根據以下未讀郵件，幫我整理成 Telegram 訊息格式。

分類：
1. 重要郵件
2. 待回覆郵件
3. 廣告或垃圾郵件
4. 可以先封存的郵件

請用繁體中文，簡潔整理。
請保留每封郵件的重要度分數。
不要建議封存重要郵件、銀行安全通知、學校通知、實習通知。

郵件內容：
{email_text}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text