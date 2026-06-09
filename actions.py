import json
from gmail_service import get_gmail_service

def archive_email(message_id):
    service = get_gmail_service()

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "removeLabelIds": ["INBOX"]
        }
    ).execute()

    return True


def get_archive_candidates():
    with open("last_emails.json", "r", encoding="utf-8") as f:
        emails = json.load(f)

    candidates = []

    for mail in emails:
        importance = mail.get("importance", {})

        if importance.get("can_archive") is True:
            candidates.append(mail)

    with open("archive_candidates.json", "w", encoding="utf-8") as f:
        json.dump(
            candidates,
            f,
            ensure_ascii=False,
            indent=2
        )

    return candidates


def confirm_archive_candidates():
    with open("archive_candidates.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)

    archived = []

    for mail in candidates:
        archive_email(mail["id"])
        archived.append(mail)

    return archived