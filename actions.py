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
        ],
        "合作金庫": [
            "合作金庫",
            "合作金庫銀行",
            "tcb",
            "tcb-bank",
            "tcb bank",
            "tcb.com.tw",
            "taiwan cooperative bank"
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
        "電子綜合對帳單",
        "對帳單",
        "電子對帳單",
        "月結單",
        "月結帳單",
        "信用卡帳單",
        "信用卡電子帳單",
        "繳款通知",
        "繳費",
        "扣款",
        "應繳",
        "應繳金額"
    ]

    promo_keywords = [
        "優惠",
        "回饋",
        "點數",
        "現金回饋",
        "折扣",
        "活動",
        "信貸",
        "貸款",
        "月付金",
        "彈性規劃",
        "利率",
        "分期"
    ]

    if any(k.lower() in content for k in bill_keywords):
        return "帳單"

    if any(k.lower() in content for k in login_keywords):
        return "登入紀錄"

    if any(k.lower() in content for k in withdraw_keywords):
        return "提款通知"

    if any(k.lower() in content for k in transfer_keywords):
        return "轉帳通知"

    if any(k.lower() in content for k in card_keywords):
        return "信用卡"

    if any(k.lower() in content for k in promo_keywords):
        return "優惠"

    return "一般通知"


def detect_security_label(content, subject=""):
    security_rules = [
        (
            "AI/安全/帳戶異常",
            [
                "登入失敗",
                "異常登入",
                "帳戶異常",
                "可疑活動",
                "suspicious activity",
                "unknown device",
                "未知裝置",
                "不明裝置",
                "帳戶遭到",
                "account alert"
            ]
        ),
        (
            "AI/安全/Passkey",
            [
                "passkey",
                "通行密鑰",
                "安全金鑰"
            ]
        ),
        (
            "AI/安全/第三方授權",
            [
                "oauth",
                "第三方存取",
                "第三方授權",
                "third-party access",
                "third party access",
                "帳戶存取",
                "account access",
                "帳戶資料",
                "google 帳戶資料",
                "分享了部分 google 帳戶資料",
                "可存取您的部分 google 帳戶資料"
            ]
        ),
        (
            "AI/安全/密碼",
            [
                "密碼變更",
                "密碼已變更",
                "修改密碼",
                "重設密碼",
                "忘記密碼",
                "密碼異常",
                "password changed",
                "password reset",
                "reset password",
                "new password",
                "變更密碼"
            ]
        ),
        (
            "AI/安全/驗證",
            [
                "驗證碼",
                "verification",
                "otp",
                "one-time password",
                "兩步驟驗證",
                "雙重驗證"
            ]
        ),
        (
            "AI/安全/登入紀錄",
            [
                "登入成功",
                "登入失敗",
                "登入通知",
                "sign-in",
                "new sign-in",
                "新登入",
                "新裝置",
                "new device",
                "登入活動",
                "新登入活動"
            ]
        ),
        (
            "AI/安全/一般",
            [
                "安全性快訊",
                "安全通知",
                "安全性通知",
                "安全提醒",
                "security alert",
                "security notice",
                "google 帳戶",
                "account security"
            ]
        )
    ]

    search_targets = []

    if subject:
        search_targets.append(subject.lower())

    search_targets.append(content)

    for target in search_targets:
        for label_name, keywords in security_rules:
            if any(keyword.lower() in target for keyword in keywords):
                return label_name

    return None


def detect_general_label(content, importance, subject=""):
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

    security_label = detect_security_label(content, subject)
    if security_label:
        return security_label

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
            label_name = detect_general_label(content, importance, subject)

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
