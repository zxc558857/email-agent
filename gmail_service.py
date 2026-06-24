import os
import base64
import json

from mail_rules import score_email
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