def _mail_text(mail):
    return f"{mail.get('from', '')} {mail.get('subject', '')} {mail.get('snippet', '')}".lower()


def _subject_text(mail):
    return (mail.get("subject", "") or "").lower()


def _contains_any(text, keywords):
    return any(keyword.lower() in text for keyword in keywords)


PROMOTION_KEYWORDS = [
    "優惠",
    "回饋",
    "限時",
    "領券",
    "抽獎",
    "抽",
    "問卷",
    "調查",
    "活動",
    "推廣",
    "webinar",
    "新品",
    "特惠",
    "折扣",
    "折價券",
    "優惠券",
    "折扣券",
    "購物金",
    "% off",
    " off",
    "coupon",
    "voucher",
    "promo code",
    "discount code",
    "discount",
    "deal",
    "ends tomorrow",
    "limited time",
    "save",
    "upgrade offer",
    "sale",
    "promotion",
    "survey",
    "newsletter",
    "電子報",
    "廣告",
]

PAYMENT_SUCCESS_KEYWORDS = [
    "已付款",
    "付款成功",
    "付款狀態 更新為: 已付款",
    "付款狀態更新為已付款",
    "訂單完成",
    "謝謝你的訂單",
    "訂單成立",
    "payment successful",
    "payment received",
    "order confirmed",
]

PAYMENT_FAILURE_KEYWORDS = [
    "付款失敗",
    "扣款失敗",
    "交易失敗",
    "退款異常",
    "未授權交易",
    "信用卡異常交易",
    "payment failed",
    "transaction failed",
    "unauthorized transaction",
]

HIGH_SECURITY_KEYWORDS = [
    "登入失敗",
    "登入「失敗」",
    "異常登入",
    "可疑登入",
    "可疑活動",
    "帳戶遭鎖定",
    "帳戶異常",
    "未知裝置",
    "不明裝置",
    "unknown device",
    "suspicious activity",
    "密碼變更",
    "密碼已變更",
    "修改密碼",
    "重設密碼",
    "密碼重置",
    "忘記密碼",
    "密碼異常",
    "變更密碼",
    "password changed",
    "password reset",
    "reset password",
    "new password",
    "passkey",
    "通行密鑰",
    "安全金鑰",
    "第三方存取權新增",
    "第三方存取",
    "第三方授權",
    "third-party access",
    "third party access",
    "oauth",
    "可存取您的部分 google 帳戶資料",
    "分享了部分 google 帳戶資料",
    "帳戶存取",
    "account access",
]

SECURITY_NOTICE_KEYWORDS = [
    "安全性快訊",
    "安全通知",
    "安全性通知",
    "安全提醒",
    "security alert",
    "security notice",
    "account security",
    "google 帳戶",
]

LOGIN_SUCCESS_KEYWORDS = [
    "登入成功",
    "登入「成功」",
    "登入成功通知",
    "行動銀行app登入成功",
    "行動銀行 app 登入成功",
    "生物辨識登入成功",
    "login success",
]

LOGIN_FAILURE_KEYWORDS = [
    "登入失敗",
    "登入「失敗」",
    "異常登入",
    "可疑登入",
    "登入異常",
    "login failed",
    "failed login",
]

LOGIN_NOTICE_KEYWORDS = [
    "登入通知",
    "新登入通知",
    "新登入",
    "新裝置登入",
    "登入活動",
    "新登入活動",
    "sign-in",
    "new sign-in",
    "new device",
]

BILL_KEYWORDS = [
    "電子對帳單",
    "電子綜合對帳單",
    "綜合對帳單",
    "銀行對帳單",
    "信用卡帳單",
    "信用卡電子帳單",
    "電子帳單",
    "月結帳單",
    "statement",
    "e-statement",
]

JOB_RECOMMENDATION_KEYWORDS = [
    "新職務",
    "新職缺",
    "推薦職缺",
    "你可能有興趣的工作",
    "關注的公司刊登職務",
    "刊登新職務",
]

JOB_HIGH_IMPORTANCE_KEYWORDS = [
    "面試邀請",
    "面試通知",
    "錄取通知",
    "應徵結果",
    "請回覆面試時間",
    "請確認面試",
    "請確認可面試時間",
    "job offer",
    "offer letter",
]

FORMAL_RESULT_KEYWORDS = [
    "審核通過",
    "核准",
    "交易成功",
    "續貸",
    "撥款通知",
]

WORK_ACTION_KEYWORDS = [
    "請回覆",
    "請確認",
    "請提供",
    "請填寫",
    "請於",
    "期限",
    "deadline",
    "rsvp",
    "是否參加",
    "審核結果",
    "申請結果",
    "實習",
    "研揚",
    "中國科技大學",
    "學校",
]

ARCHIVE_KEYWORDS = [
    "linkedin",
    "toplink",
    "電子報",
    "newsletter",
    "優惠",
    "折扣",
    "折價券",
    "優惠券",
    "折扣券",
    "購物金",
    "活動通知",
    "免費票",
    "新品",
    "% off",
    "coupon",
    "voucher",
    "promo code",
    "discount code",
    "discount",
    "deal",
    "ends tomorrow",
    "limited time",
    "upgrade offer",
    "promotion",
    "sale",
]

NEVER_ARCHIVE_KEYWORDS = [
    "登入失敗",
    "異常登入",
    "可疑登入",
    "安全性",
    "驗證碼",
    "銀行",
    "line bank",
    "中國信託",
    "台北富邦",
    "研揚",
    "實習",
    "學校",
    "富邦人壽",
    "合作金庫",
    "security alert",
    "security notice",
    "passkey",
    "oauth",
    "third-party access",
    "third party access",
    "account access",
    "suspicious activity",
    "new sign-in",
    "sign-in",
    "new device",
    "password changed",
    "password reset",
    "reset password",
    "new password",
    "密碼變更",
    "密碼已變更",
    "修改密碼",
    "重設密碼",
    "密碼異常",
    "google 帳戶",
    "帳戶存取",
    "帳戶資料",
]

NO_REPLY_KEYWORDS = [
    *PROMOTION_KEYWORDS,
    *PAYMENT_SUCCESS_KEYWORDS,
    "api pricing",
    "pricing announcement",
    "價格公告",
    "系統通知",
    "登入成功",
    "對帳單",
    "電子帳單",
    "帳單",
    "訂單完成",
    "商品推廣",
]

NOTIFICATION_RECEIPT_KEYWORDS = [
    "繳款證明",
    "付款證明",
    "收款證明",
    "交易通知",
    "付款成功",
    "已付款",
    "訂單完成",
    "電子收據",
    "收據",
    "receipt",
    "payment confirmation",
    "transaction notification",
    "order confirmation",
]

NOTIFICATION_NO_REPLY_KEYWORDS = [
    "會員確認信",
    "帳號確認",
    "email verification",
    "verify email",
    "confirmation email",
    "活動通知",
    "行銷技巧",
    "推廣內容",
    "電子報",
    "newsletter",
    "系統通知",
    "大促成功秘訣",
]

STRONG_REPLY_REQUEST_KEYWORDS = [
    "請回覆",
    "請回信",
    "回覆此信",
    "麻煩回覆",
    "請回覆確認",
    "請確認並回覆",
    "是否參加",
    "rsvp",
    "reply to this email",
    "please reply",
    "please respond",
    "please send the requested information",
    "please provide the requested information",
]

DIRECT_REPLY_REQUEST_KEYWORDS = [
    keyword
    for keyword in STRONG_REPLY_REQUEST_KEYWORDS
    if keyword != "回覆此信"
]

REPLY_REQUEST_KEYWORDS = [
    *STRONG_REPLY_REQUEST_KEYWORDS,
    "請提供",
    "請告知",
    "是否可以",
    "能否",
    "可否",
    "please confirm",
    "please provide",
]


def _score_level(score):
    if score >= 80:
        return "🔴 高重要"
    if score >= 40:
        return "🟡 中重要"
    return "⚪ 低重要"


def _is_login_failure(subject):
    return _contains_any(subject, LOGIN_FAILURE_KEYWORDS) or (
        "登入" in subject
        and _contains_any(subject, ["失敗", "異常", "可疑", "unknown", "failed"])
    )


def _is_login_success(subject):
    return _contains_any(subject, LOGIN_SUCCESS_KEYWORDS) or (
        "登入" in subject
        and _contains_any(subject, ["成功", "success"])
    )


def score_email(mail):
    text = _mail_text(mail)
    subject = _subject_text(mail)
    score = 45
    tags = []

    is_login_failure = _is_login_failure(subject)
    is_login_success = _is_login_success(subject)
    is_login_notice = _contains_any(subject, LOGIN_NOTICE_KEYWORDS)
    is_payment_failure = _contains_any(text, PAYMENT_FAILURE_KEYWORDS)
    is_payment_success = _contains_any(subject, PAYMENT_SUCCESS_KEYWORDS)
    subject_has_high_security = _contains_any(subject, HIGH_SECURITY_KEYWORDS)
    is_high_security = subject_has_high_security or (
        _contains_any(text, HIGH_SECURITY_KEYWORDS) and not is_payment_success
    )
    is_security_notice = is_high_security or _contains_any(text, SECURITY_NOTICE_KEYWORDS)
    is_bill = _contains_any(subject, BILL_KEYWORDS)
    is_promotion = _contains_any(subject, PROMOTION_KEYWORDS)
    is_job_recommendation = _contains_any(subject, JOB_RECOMMENDATION_KEYWORDS)
    is_job_high_importance = _contains_any(text, JOB_HIGH_IMPORTANCE_KEYWORDS)
    is_formal_result = _contains_any(subject, FORMAL_RESULT_KEYWORDS)
    has_work_action = _contains_any(text, WORK_ACTION_KEYWORDS)

    if is_payment_failure or is_login_failure:
        score = 90
        tags.extend(["重要", "異常"])
    elif is_high_security:
        score = 90
        tags.extend(["安全", "重要"])
    elif is_promotion and not is_high_security:
        score = 25
        tags.extend(["低風險", "推廣"])
    elif is_security_notice:
        score = 80
        tags.extend(["安全", "重要"])
    elif is_login_success:
        score = 60
        tags.append("登入紀錄")
    elif is_bill:
        score = 80
        tags.append("帳單")
    elif is_login_notice:
        score = 70
        tags.append("登入紀錄")
    elif is_payment_success:
        score = 35
        tags.append("付款成功")
    elif is_job_recommendation:
        score = 50
        tags.append("職缺推薦")
    elif is_job_high_importance:
        score = 85
        tags.append("求職重要")
    elif is_formal_result:
        score = 80
        tags.append("正式結果")
    elif has_work_action:
        score = 80
        tags.append("需要處理")

    can_archive = score <= 30

    if _contains_any(text, ARCHIVE_KEYWORDS):
        can_archive = True

    if _contains_any(text, NEVER_ARCHIVE_KEYWORDS):
        can_archive = False

    score = max(0, min(100, score))

    return {
        "score": score,
        "level": _score_level(score),
        "tags": list(set(tags)),
        "can_archive": can_archive,
    }


def needs_reply(mail):
    text = _mail_text(mail)
    subject = _subject_text(mail)

    if _contains_any(subject, NOTIFICATION_RECEIPT_KEYWORDS) and not _contains_any(
        text,
        STRONG_REPLY_REQUEST_KEYWORDS,
    ):
        return False

    if _contains_any(text, NOTIFICATION_NO_REPLY_KEYWORDS) and not _contains_any(
        text,
        DIRECT_REPLY_REQUEST_KEYWORDS,
    ):
        return False

    if not _contains_any(text, REPLY_REQUEST_KEYWORDS):
        return False

    if _contains_any(subject, NO_REPLY_KEYWORDS):
        return False

    return True
