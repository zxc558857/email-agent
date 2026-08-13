from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actions import detect_bank_label, detect_finance_type, detect_general_label
from mail_rules import score_email


def classify(mail):
    importance = score_email(mail)
    content = (
        f"{mail.get('subject', '')} "
        f"{mail.get('from', '')} "
        f"{mail.get('snippet', '')}"
    ).lower()

    bank_name = detect_bank_label(content)

    if bank_name:
        label = f"AI/金融/{bank_name}/{detect_finance_type(content)}"
    else:
        label = detect_general_label(content, importance, mail.get("subject", ""))

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


def run():
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


if __name__ == "__main__":
    run()
    print("ALL_V211_REGRESSION_TESTS_PASSED")
