import json
from gmail_service import get_gmail_service, get_unread_emails, get_or_create_label


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


def detect_bank_label(content):
    bank_rules = {
        "中國信託": [
            "中國信託",
            "ctbc",
            "ctbcbank",
            "bank.cs",
            "中國信託銀行"
        ],
        "LINE Bank": [
            "line bank",
            "linebank",
            "line bank連線商業銀行"
        ],
        "富邦": [
            "富邦",
            "fubon",
            "taipeifubon",
            "台北富邦"
        ],
        "國泰世華": [
            "國泰",
            "cathay",
            "cathaybk",
            "國泰世華"
        ],
        "永豐": [
            "永豐",
            "sinopac"
        ],
        "玉山": [
            "玉山",
            "esun"
        ],
        "元大": [
            "元大",
            "yuanta"
        ],
        "台新": [
            "台新",
            "taishin"
        ]
    }

    for bank_name, keywords in bank_rules.items():
        for keyword in keywords:
            if keyword.lower() in content:
                return bank_name

    return None


def detect_finance_type(content):
    login_keywords = [
        "登入",
        "login",
        "登入成功",
        "登入失敗",
        "安全通知",
        "安全性通知",
        "安全提醒",
        "驗證",
        "otp",
        "裝置",
        "ip",
        "異常",
        "密碼"
    ]

    withdraw_keywords = [
        "提款",
        "無卡提款",
        "提款交易",
        "提款預約"
    ]

    transfer_keywords = [
        "轉帳",
        "匯款",
        "交易結果",
        "交易通知"
    ]

    card_keywords = [
        "信用卡",
        "刷卡",
        "消費通知",
        "卡片",
        "簽帳金融卡",
        "金融卡"
    ]

    bill_keywords = [
        "帳單",
        "電子帳單",
        "繳費",
        "扣款",
        "對帳單",
        "應繳"
    ]

    promo_keywords = [
        "優惠",
        "回饋",
        "點數",
        "現金回饋",
        "折扣",
        "活動"
    ]

    if any(k.lower() in content for k in login_keywords):
        return "登入紀錄"

    if any(k.lower() in content for k in withdraw_keywords):
        return "提款通知"

    if any(k.lower() in content for k in transfer_keywords):
        return "轉帳通知"

    if any(k.lower() in content for k in card_keywords):
        return "信用卡"

    if any(k.lower() in content for k in bill_keywords):
        return "帳單"

    if any(k.lower() in content for k in promo_keywords):
        return "優惠"

    return "一般通知"


def detect_general_label(content, importance):
    score = importance.get("score", 50)
    can_archive = importance.get("can_archive", False)

    work_keywords = [
        "面試",
        "錄取",
        "offer",
        "履歷",
        "應徵",
        "實習",
        "研揚",
        "104",
        "1111",
        "yes123",
        "cake"
    ]

    school_keywords = [
        "中國科技大學",
        "學校",
        "課程",
        "成績",
        "註冊",
        "繳費單",
        "學生"
    ]

    ai_keywords = [
        "openai",
        "anthropic",
        "claude",
        "github",
        "codecademy",
        "python",
        "developer",
        "api"
    ]

    social_keywords = [
        "linkedin",
        "facebook",
        "instagram",
        "messenger",
        "threads"
    ]

    shopping_keywords = [
        "蝦皮",
        "momo",
        "pchome",
        "costco",
        "apple",
        "訂單",
        "收據",
        "發票"
    ]

    ad_keywords = [
        "foodpanda",
        "uber eats",
        "ubereats",
        "kkday",
        "klook",
        "toplink",
        "優惠券",
        "折價券",
        "展覽",
        "廣告",
        "newsletter",
        "promotion",
        "sale",
        "折扣"
    ]

    if any(k.lower() in content for k in work_keywords):
        return "AI/工作"

    if any(k.lower() in content for k in school_keywords):
        return "AI/學校"

    if any(k.lower() in content for k in ai_keywords):
        return "AI/AI資訊"

    if any(k.lower() in content for k in shopping_keywords):
        return "AI/購物"

    if any(k.lower() in content for k in social_keywords):
        return "AI/社群"

    if any(k.lower() in content for k in ad_keywords):
        return "AI/可封存"

    if score >= 80:
        return "AI/重要"

    if can_archive or score <= 30:
        return "AI/可封存"

    return "AI/一般"


def auto_label_emails():
    emails = get_unread_emails(limit=20)

    labeled = []

    service = get_gmail_service()

    for mail in emails:
        subject = mail.get("subject", "")
        sender = mail.get("from", "")
        snippet = mail.get("snippet", "")
        importance = mail.get("importance", {})

        content = f"{subject} {sender} {snippet}".lower()

        bank_name = detect_bank_label(content)

        if bank_name:
            finance_type = detect_finance_type(content)
            label_name = f"AI/金融/{bank_name}/{finance_type}"
        else:
            label_name = detect_general_label(content, importance)

        try:
            label_id = get_or_create_label(label_name)

            service.users().messages().modify(
                userId="me",
                id=mail["id"],
                body={
                    "addLabelIds": [label_id]
                }
            ).execute()

            labeled.append({
                "subject": subject,
                "label": label_name
            })

        except Exception as e:
            print(f"標籤失敗：{subject}")
            print(e)

    return labeled