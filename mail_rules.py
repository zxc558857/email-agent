def score_email(mail):
    text = f"{mail.get('from','')} {mail.get('subject','')} {mail.get('snippet','')}".lower()

    score = 50
    tags = []

    high_keywords = [
        "登入失敗", "異常登入", "安全性", "驗證碼", "密碼",
        "研揚", "實習", "學校", "中國科技大學",
        "付款", "帳單", "保險", "富邦", "銀行"
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
        "登入失敗", "異常登入", "安全性", "驗證碼", "密碼",
        "銀行", "line bank", "中國信託", "台北富邦",
        "研揚", "實習", "學校", "富邦人壽"
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