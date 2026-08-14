import os
import base64
import json

from mail_rules import score_email
from datetime import date, datetime, timedelta
from email import message_from_bytes

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def get_unread_emails(limit=10):
    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=limit
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = msg_data.get("payload", {}).get("headers", [])

        email_info = {
            "id": msg["id"],
            "from": "",
            "subject": "",
            "date": "",
            "snippet": msg_data.get("snippet", "")
        }

        for h in headers:
            if h["name"] == "From":
                email_info["from"] = h["value"]
            elif h["name"] == "Subject":
                email_info["subject"] = h["value"]
            elif h["name"] == "Date":
                email_info["date"] = h["value"]

        email_info["importance"] = score_email(email_info)
        emails.append(email_info)

    with open("last_emails.json", "w", encoding="utf-8") as f:
        json.dump(
            emails,
            f,
            ensure_ascii=False,
            indent=2
        )
    return emails


def _format_gmail_search_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        value = value.date()
    elif isinstance(value, str):
        value = date.fromisoformat(value)

    return value.strftime("%Y/%m/%d")


def _build_index_query(days=90, date_from=None, date_to=None, query=None):
    parts = []

    if query:
        parts.append(query)

    if date_from:
        parts.append(f"after:{_format_gmail_search_date(date_from)}")
    elif days:
        start_date = date.today() - timedelta(days=days)
        parts.append(f"after:{_format_gmail_search_date(start_date)}")

    if date_to:
        end_date = date_to
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        # Gmail before: is exclusive, so add one day for inclusive date_to.
        parts.append(f"before:{_format_gmail_search_date(end_date + timedelta(days=1))}")

    return " ".join(parts)


def get_emails_for_index(days=90, date_from=None, date_to=None, limit=None, query=None):
    service = get_gmail_service()
    gmail_query = _build_index_query(
        days=days,
        date_from=date_from,
        date_to=date_to,
        query=query,
    )

    emails = []
    page_token = None

    while True:
        request = {
            "userId": "me",
            "q": gmail_query,
            "maxResults": min(500, limit - len(emails)) if limit else 500,
        }

        if page_token:
            request["pageToken"] = page_token

        results = service.users().messages().list(**request).execute()
        messages = results.get("messages", [])

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = msg_data.get("payload", {}).get("headers", [])

            email_info = {
                "id": msg["id"],
                "thread_id": msg_data.get("threadId", ""),
                "internal_date": msg_data.get("internalDate"),
                "from": "",
                "subject": "",
                "date": "",
                "snippet": msg_data.get("snippet", ""),
                "label_ids": msg_data.get("labelIds", []),
            }

            for h in headers:
                name = h.get("name")
                if name == "From":
                    email_info["from"] = h.get("value", "")
                elif name == "Subject":
                    email_info["subject"] = h.get("value", "")
                elif name == "Date":
                    email_info["date"] = h.get("value", "")

            email_info["importance"] = score_email(email_info)
            emails.append(email_info)

            if limit and len(emails) >= limit:
                return emails

        page_token = results.get("nextPageToken")
        if not page_token:
            return emails


def get_or_create_label(label_name):
    service = get_gmail_service()

    labels = service.users().labels().list(
        userId="me"
    ).execute().get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    new_label = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
    ).execute()

    return new_label["id"]


def add_label_to_email(message_id, label_name):
    service = get_gmail_service()

    label_id = get_or_create_label(label_name)

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": [label_id]
        }
    ).execute()

    return True
