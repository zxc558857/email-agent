import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from mail_rules import needs_reply, score_email

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

IMPORTANT_SCORE_THRESHOLD = 80
PROMOTION_SCORE_THRESHOLD = 45

IMPORTANT_TITLE = "\U0001f6a8\u3010\u91cd\u8981\u90f5\u4ef6\u3011\U0001f6a8"
REPLY_TITLE = "\U0001f4e9\u3010\u5f85\u56de\u8986\u90f5\u4ef6\u3011\U0001f4e9"
PROMOTION_TITLE = "\U0001f4e2\u3010\u5ee3\u544a\u6216\u63a8\u5ee3\u90f5\u4ef6\u3011\U0001f4e2"
ARCHIVE_TITLE = "\U0001f4c2\u3010\u5176\u4ed6\u53ef\u4ee5\u5148\u5c01\u5b58\u7684\u90f5\u4ef6\u3011\U0001f4c2"
EMPTY_TEXT = "\u7121"


def _importance_for(mail):
    importance = mail.get("importance")
    if not importance:
        if "importance_score" in mail or "importance_level" in mail or "can_archive" in mail:
            importance = {
                "score": mail.get("importance_score", 0),
                "level": mail.get("importance_level", ""),
                "can_archive": mail.get("can_archive", False),
            }
        else:
            importance = score_email(mail)

    score = importance.get("score", mail.get("importance_score", 0))
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 0

    return {
        "score": score,
        "level": importance.get("level", mail.get("importance_level", "")),
        "can_archive": importance.get("can_archive", mail.get("can_archive", False)) == True,
    }


def _mail_identity(mail, index):
    return str(mail.get("id") or mail.get("message_id") or mail.get("thread_id") or index)


def _dedupe(items):
    seen = set()
    unique = []

    for item in items:
        key = item["message_key"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


def _preclassify_emails(emails):
    classified = []

    for index, mail in enumerate(emails, start=1):
        importance = _importance_for(mail)
        item = {
            "id": str(index),
            "message_key": _mail_identity(mail, index),
            "from": mail.get("from", ""),
            "subject": mail.get("subject", ""),
            "snippet": mail.get("snippet", ""),
            "importance_score": importance["score"],
            "importance_level": importance["level"],
            "needs_reply": needs_reply(mail),
            "can_archive": importance["can_archive"],
        }
        classified.append(item)

    important_emails = _dedupe(
        item
        for item in classified
        if item["importance_score"] >= IMPORTANT_SCORE_THRESHOLD
    )
    important_keys = {item["message_key"] for item in important_emails}

    reply_emails = _dedupe(
        item
        for item in classified
        if item["needs_reply"] is True and item["message_key"] not in important_keys
    )
    reply_keys = {item["message_key"] for item in reply_emails}

    promotional_emails = _dedupe(
        item
        for item in classified
        if item["importance_score"] < IMPORTANT_SCORE_THRESHOLD
        and item["needs_reply"] is False
        and item["importance_score"] <= PROMOTION_SCORE_THRESHOLD
        and item["message_key"] not in important_keys
        and item["message_key"] not in reply_keys
    )
    promotion_keys = {item["message_key"] for item in promotional_emails}

    archive_emails = _dedupe(
        item
        for item in classified
        if item["can_archive"] is True
        and item["message_key"] not in important_keys
        and item["message_key"] not in reply_keys
        and item["message_key"] not in promotion_keys
    )

    return {
        "all": classified,
        "important": important_emails,
        "reply": reply_emails,
        "promotion": promotional_emails,
        "archive": archive_emails,
    }


def _format_mail_for_prompt(item):
    return f"""
ID: {item['id']}
importance: {item['importance_level']} | {item['importance_score']}
rule_flags: important={item['importance_score'] >= IMPORTANT_SCORE_THRESHOLD}, needs_reply={item['needs_reply']}, can_archive={item['can_archive']}
from: {item['from']}
subject: {item['subject']}
snippet: {item['snippet']}
"""


def _load_ai_summaries(output_text):
    try:
        data = json.loads(output_text)
    except (TypeError, json.JSONDecodeError):
        return {}

    summaries = data.get("summaries", data)
    if not isinstance(summaries, dict):
        return {}

    normalized = {}
    for mail_id, value in summaries.items():
        if isinstance(value, str):
            normalized[str(mail_id)] = {"summary": value, "action": ""}
        elif isinstance(value, dict):
            normalized[str(mail_id)] = {
                "summary": str(value.get("summary", "")).strip(),
                "action": str(value.get("action", "")).strip(),
            }

    return normalized


def _fallback_summary(item):
    snippet = item["snippet"].strip()
    if snippet:
        return snippet[:80]
    return "\u8acb\u67e5\u770b\u90f5\u4ef6\u5167\u5bb9\u3002"


def _sanitize_action(item, action):
    if not action:
        return ""

    lowered = action.lower()
    if item["can_archive"] is False and (
        "\u5c01\u5b58" in action or "archive" in lowered
    ):
        return ""

    if item["needs_reply"] is False and (
        "\u56de\u8986" in action
        or "\u8acb\u78ba\u8a8d" in action
        or "\u8acb\u63d0\u4f9b" in action
        or "reply" in lowered
        or "confirm" in lowered
        or "provide" in lowered
    ):
        return ""

    return action


def _render_item(item, ai_summaries):
    ai_summary = ai_summaries.get(item["id"], {})
    summary = ai_summary.get("summary") or _fallback_summary(item)
    action = _sanitize_action(item, ai_summary.get("action"))

    lines = [
        f"- {item['subject']}\uff08{item['importance_score']}\u5206\uff09",
        f"  \u5bc4\u4ef6\u8005\uff1a{item['from']}",
        f"  \u6458\u8981\uff1a{summary}",
    ]
    if action:
        lines.append(f"  \u5efa\u8b70\uff1a{action}")

    return "\n".join(lines)


def _render_section(title, emails, ai_summaries):
    if not emails:
        return f"{title}\n{EMPTY_TEXT}"

    rendered = "\n".join(_render_item(item, ai_summaries) for item in emails)
    return f"{title}\n{rendered}"


def summarize_emails(emails):
    if not emails:
        return "\U0001f4ed \u76ee\u524d\u6c92\u6709\u672a\u8b80\u90f5\u4ef6\u3002"

    classified = _preclassify_emails(emails)
    email_text = "\n".join(
        _format_mail_for_prompt(item) for item in classified["all"]
    )

    prompt = f"""
You are a personal email assistant.

Python has already classified every email. Do not classify, move, or add emails.
Only write a Traditional Chinese 1-2 line summary and a short action suggestion
for each ID.

Hard rules:
- Important emails are decided only by Python: importance_score >= 80.
- Reply emails are decided only by Python: needs_reply == true.
- Archive emails are decided only by Python: can_archive == true.
- Do not output Telegram sections or category names.

Return JSON only:
{{
  "summaries": {{
    "1": {{"summary": "summary", "action": "suggestion"}},
    "2": {{"summary": "summary", "action": ""}}
  }}
}}

Emails:
{email_text}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    ai_summaries = _load_ai_summaries(response.output_text)

    sections = [
        _render_section(IMPORTANT_TITLE, classified["important"], ai_summaries),
        _render_section(REPLY_TITLE, classified["reply"], ai_summaries),
        _render_section(PROMOTION_TITLE, classified["promotion"], ai_summaries),
        _render_section(ARCHIVE_TITLE, classified["archive"], ai_summaries),
    ]

    return "\n\n".join(sections)
