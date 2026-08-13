def score_email(mail):
    text = f"{mail.get('from','')} {mail.get('subject','')} {mail.get('snippet','')}".lower()

    score = 50
    tags = []

    high_security_keywords = [
        "登入失敗", "異常登入", "可疑活動", "suspicious activity",
        "密碼變更", "密碼已變更", "修改密碼", "重設密碼",
        "忘記密碼", "密碼異常", "變更密碼",
        "password changed", "password reset", "reset password",
        "new password", "帳戶異常",
        "未知裝置", "不明裝置", "unknown device",
        "第三方存取權新增", "第三方存取", "第三方授權",
        "third-party access", "third party access", "oauth",
        "可存取您的部分 google 帳戶資料", "帳戶存取", "account access"
    ]

    security_keywords = [
        "安全性快訊", "安全通知", "安全性通知", "安全提醒",
        "security alert", "security notice",
        "登入成功", "登入失敗", "登入通知", "sign-in", "new sign-in",
        "新登入", "新裝置", "new device", "登入活動", "新登入活動",
        "passkey", "通行密鑰", "安全金鑰",
        "驗證碼", "verification", "otp", "兩步驟驗證", "雙重驗證",
        "帳戶資料", "google 帳戶", "分享了部分 google 帳戶資料",
        "帳戶異常", "account security"
    ]

    is_high_security = any(word.lower() in text for word in high_security_keywords)
    is_security = is_high_security or any(word.lower() in text for word in security_keywords)

    high_keywords = [
        "登入失敗", "異常登入", "安全性", "驗證碼",
        "研揚", "實習", "學校", "中國科技大學",
        "付款", "帳單", "保險", "富邦", "銀行", "合作金庫"
    ]

    low_keywords = [
        "linkedin", "toplink", "優惠", "折扣", "免費票",
        "活動", "電子報", "newsletter", "promotion", "sale"
    ]

    archive_keywords = [
        "linkedin", "toplink", "電子報", "優惠", "折扣",
        "活動通知", "免費票"
    ]

    never_archive_keywords = [
        "登入失敗", "異常登入", "安全性", "驗證碼",
        "銀行", "line bank", "中國信託", "台北富邦",
        "研揚", "實習", "學校", "富邦人壽", "合作金庫",
        "security alert", "security notice", "passkey",
        "oauth", "third-party access", "third party access",
        "account access", "suspicious activity", "new sign-in",
        "sign-in", "new device", "password changed",
        "password reset", "reset password", "new password",
        "密碼變更", "密碼已變更", "修改密碼", "重設密碼", "密碼異常",
        "google 帳戶", "帳戶存取", "帳戶資料"
    ]

    for word in high_keywords:
        if word.lower() in text:
            score += 25
            tags.append("重要")

    for word in low_keywords:
        if word.lower() in text:
            score -= 30
            tags.append("低風險")

    score = max(0, min(100, score))

    can_archive = False

    if score <= 30:
        can_archive = True

    for word in archive_keywords:
        if word.lower() in text:
            can_archive = True

    for word in never_archive_keywords:
        if word.lower() in text:
            can_archive = False

    if is_high_security:
        score = max(score, 80)
        can_archive = False
        tags.append("安全")
        tags.append("重要")
    elif is_security:
        score = max(score, 50)
        can_archive = False
        tags.append("安全")

    if score >= 80:
        level = "🔴 高重要"
    elif score >= 50:
        level = "🟡 中重要"
    else:
        level = "⚪ 低重要"

    return {
        "score": score,
        "level": level,
        "tags": list(set(tags)),
        "can_archive": can_archive
    }
