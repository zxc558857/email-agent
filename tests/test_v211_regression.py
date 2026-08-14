from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actions import determine_email_classification, detect_finance_type
from mail_rules import score_email


def classify(mail):
    importance = score_email(mail)
    mail = {**mail, "importance": importance}
    label = determine_email_classification(mail)["label"]

    return label, importance


def assert_case(name, mail, expected_label, expected_archive=False):
    label, importance = classify(mail)

    assert label == expected_label, (
        f"{name}: expected label {expected_label}, got {label}"
    )
    assert importance["can_archive"] is expected_archive, (
        f"{name}: expected can_archive {expected_archive}, "
        f"got {importance['can_archive']}"
    )

    print(
        f"{name}: label={label} "
        f"score={importance['score']} "
        f"can_archive={importance['can_archive']}"
    )


def assert_not_label(name, mail, unexpected_label):
    label, importance = classify(mail)

    assert label != unexpected_label, (
        f"{name}: unexpected label {unexpected_label}"
    )

    print(
        f"{name}: label={label} "
        f"score={importance['score']} "
        f"can_archive={importance['can_archive']}"
    )


def run():
    loan_subject = "就學貸款撥款通知"
    loan_sender = "台北富邦銀行 <notice@fubon.com>"
    loan_snippet = "故意包含 電子帳單、帳單、繳款、應繳 等字樣"
    loan_content = f"{loan_subject} {loan_sender} {loan_snippet}".lower()
    assert detect_finance_type(loan_subject, loan_content) == "一般通知"

    assert_case(
        "Case A",
        {
            "from": "合作金庫銀行",
            "subject": "合作金庫銀行115年7月份電子綜合對帳單(3133)",
            "snippet": "",
        },
        "AI/金融/合作金庫/帳單",
    )

    label, importance = classify(
        {
            "from": "保險公司",
            "subject": "[Not Virus Scanned] 行動裝置保險、電子保單/契約變更批單通知",
            "snippet": "附件開啟密碼請參考通知說明",
        }
    )
    assert label != "AI/安全/密碼", f"Case B: unexpected label {label}"
    print(
        f"Case B: label={label} "
        f"score={importance['score']} "
        f"can_archive={importance['can_archive']}"
    )

    assert_case(
        "Case C",
        {
            "from": "Luma <hello@luma.com>",
            "subject": "新增 Passkey 至 Luma",
            "snippet": "",
        },
        "AI/安全/Passkey",
    )

    assert_case(
        "Case D",
        {
            "from": "Luma <hello@luma.com>",
            "subject": "Luma 新登入通知",
            "snippet": "",
        },
        "AI/安全/登入紀錄",
    )

    assert_case(
        "Case E",
        {
            "from": "Google <no-reply@accounts.google.com>",
            "subject": "您與 Claude 分享了部分 Google 帳戶資料",
            "snippet": "Claude 目前可存取您的部分 Google 帳戶資料",
        },
        "AI/安全/第三方授權",
    )

    assert_case(
        "Case E2",
        {
            "from": "Google <no-reply@accounts.google.com>",
            "subject": "您與 Akkadu AI 分享了部分 Google 帳戶資料",
            "snippet": "Akkadu AI 目前可存取您的部分 Google 帳戶資料",
        },
        "AI/安全/第三方授權",
    )

    assert_case(
        "Case F",
        {
            "from": "合作金庫銀行",
            "subject": "電子對帳單",
            "snippet": "附件開啟密碼請使用身分證字號",
        },
        "AI/金融/合作金庫/帳單",
    )

    assert_case(
        "Case G",
        {
            "from": "台新銀行",
            "subject": "月付金想輕一點？泰幸福信貸協助您彈性規劃",
            "snippet": "",
        },
        "AI/金融/台新/優惠",
        expected_archive=False,
    )

    assert_case(
        "Case H",
        {
            "from": "合作金庫銀行",
            "subject": "合作金庫電子綜合對帳單",
            "snippet": "",
        },
        "AI/金融/合作金庫/帳單",
    )

    assert_case(
        "Case I",
        {
            "from": "LINE Bank <service@linebank.com.tw>",
            "subject": "LINE Bank 電子對帳單",
            "snippet": "",
        },
        "AI/金融/LINE Bank/帳單",
    )

    assert_not_label(
        "Case J",
        {
            "from": "LINE Bank <service@linebank.com.tw>",
            "subject": "MaiCoin｜LINE Bank 綁定扣款全新登場！買幣滿千送百",
            "snippet": "",
        },
        "AI/金融/LINE Bank/帳單",
    )

    assert_not_label(
        "Case K",
        {
            "from": "LINE Bank <service@linebank.com.tw>",
            "subject": "帳戶連結設定成功",
            "snippet": "",
        },
        "AI/金融/LINE Bank/帳單",
    )

    assert_case(
        "Case L",
        {
            "from": "富邦銀行 <notice@fubon.com>",
            "subject": "登入 Fubon+ 領券抽漢來",
            "snippet": "",
        },
        "AI/金融/富邦/優惠",
    )

    assert_case(
        "Case M",
        {
            "from": "中國信託銀行 <notice@ctbcbank.com>",
            "subject": "中國信託 行動銀行APP登入成功通知",
            "snippet": "",
        },
        "AI/金融/中國信託/登入紀錄",
    )

    assert_case(
        "Case N",
        {
            "from": "中國信託銀行 <notice@ctbcbank.com>",
            "subject": "臺幣轉帳交易結果通知",
            "snippet": "請登入網路銀行查詢交易明細",
        },
        "AI/金融/中國信託/轉帳通知",
    )

    assert_not_label(
        "Case O",
        {
            "from": "OBgE TW <notice@example.com>",
            "subject": "[OBgE TW] #20260808061126896 付款狀態 更新為: 已付款",
            "snippet": "如需變更密碼，請至會員中心設定。",
        },
        "AI/安全/密碼",
    )

    assert_case(
        "Case P",
        {
            "from": "Account <security@example.com>",
            "subject": "密碼重置請求",
            "snippet": "",
        },
        "AI/安全/密碼",
    )

    assert_case(
        "Case Q",
        {
            "from": "Luma <hello@luma.com>",
            "subject": "Luma 新登入通知",
            "snippet": "",
        },
        "AI/安全/登入紀錄",
    )

    assert_not_label(
        "Case R",
        {
            "from": "Service <notice@example.com>",
            "subject": "【重要】關於統一帳戶升級的通知",
            "snippet": "請登入帳戶完成升級流程。",
        },
        "AI/安全/登入紀錄",
    )

    assert_case(
        "Case S",
        {
            "from": "國泰世華銀行 <notice@cathaybk.com.tw>",
            "subject": "國泰世華銀行綜合對帳單",
            "snippet": "",
        },
        "AI/金融/國泰世華/帳單",
    )

    assert_case(
        "Case T",
        {
            "from": "合作金庫銀行",
            "subject": "合作金庫銀行電子綜合對帳單",
            "snippet": "",
        },
        "AI/金融/合作金庫/帳單",
    )

    assert_case(
        "Case U",
        {
            "from": "中國信託銀行 <notice@ctbcbank.com>",
            "subject": "中國信託銀行電子對帳單",
            "snippet": "",
        },
        "AI/金融/中國信託/帳單",
    )

    assert_case(
        "Case V",
        {
            "from": "台北富邦銀行 <notice@fubon.com>",
            "subject": "台北富邦銀行信用卡帳單",
            "snippet": "",
        },
        "AI/金融/富邦/帳單",
    )

    assert_not_label(
        "Case W",
        {
            "from": "台北富邦銀行 <notice@fubon.com>",
            "subject": "提醒您本期信用卡帳單繳款截止日快到囉",
            "snippet": "本期帳單繳款資訊請登入查詢。",
        },
        "AI/金融/富邦/帳單",
    )

    assert_case(
        "Case X",
        {
            "from": "台北富邦銀行 <notice@fubon.com>",
            "subject": loan_subject,
            "snippet": loan_snippet,
        },
        "AI/金融/富邦/一般通知",
    )

    assert_case(
        "Case Y",
        {
            "from": "台北富邦銀行 <notice@fubon.com>",
            "subject": "台北富邦銀行2026年7月信用卡帳單",
            "snippet": "",
        },
        "AI/金融/富邦/帳單",
    )

    assert_case(
        "Case Z",
        {
            "from": "台北富邦銀行 <notice@fubon.com>",
            "subject": "台北富邦銀行2026年7月 銀行對帳單",
            "snippet": "",
        },
        "AI/金融/富邦/帳單",
    )


if __name__ == "__main__":
    run()
    print("ALL_V211_REGRESSION_TESTS_PASSED")
