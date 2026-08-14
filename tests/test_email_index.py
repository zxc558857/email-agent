from datetime import datetime, timedelta, timezone
from contextlib import closing
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import email_index


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def fake_mail(
    message_id,
    subject,
    sender,
    snippet="",
    internal_date=None,
    labels=None,
    importance=None,
):
    return {
        "id": message_id,
        "thread_id": f"thread-{message_id}",
        "internal_date": internal_date or NOW,
        "date": "Thu, 13 Aug 2026 10:00:00 +0000",
        "from": sender,
        "subject": subject,
        "snippet": snippet,
        "label_ids": labels if labels is not None else ["INBOX", "UNREAD"],
        "importance": importance
        or {
            "score": 50,
            "level": "中等重要",
            "tags": [],
            "can_archive": False,
        },
    }


def fake_fetcher(emails):
    def fetcher(days=90, date_from=None, date_to=None, limit=None):
        return emails[:limit] if limit is not None else emails

    return fetcher


class InterruptingMail:
    def get(self, key, default=None):
        raise KeyboardInterrupt


class FakeExecute:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeMessages:
    def __init__(self, messages):
        self.messages = messages

    def get(self, userId, id, format, metadataHeaders):
        return FakeExecute(self.messages[id])


class FakeUsers:
    def __init__(self, messages):
        self._messages = FakeMessages(messages)

    def messages(self):
        return self._messages


class FakeGmailService:
    def __init__(self, messages):
        self._users = FakeUsers(messages)

    def users(self):
        return self._users


def fake_gmail_metadata(message_id, subject, sender, snippet):
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": str(int(NOW.timestamp() * 1000)),
        "snippet": snippet,
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Thu, 13 Aug 2026 10:00:00 +0000"},
            ]
        },
    }


class EmailIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "email_index.db"

    def tearDown(self):
        self.tmp.cleanup()

    def count_rows(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]

    def insert_stale_student_loan_bill_row(self, message_id):
        email_index.init_db(self.db_path)
        row = {
            "message_id": message_id,
            "thread_id": f"thread-{message_id}",
            "internal_date": email_index._to_internal_date_ms(NOW),
            "date_text": "Thu, 13 Aug 2026 10:00:00 +0000",
            "sender": "台北富邦銀行 <notice@fubon.com>",
            "sender_email": "notice@fubon.com",
            "subject": "就學貸款撥款通知",
            "snippet": "舊資料誤判為帳單",
            "importance_score": 75,
            "importance_level": "mid",
            "can_archive": 0,
            "category_label": "AI/金融/富邦/帳單",
            "bank_name": "富邦",
            "finance_type": "帳單",
            "security_type": None,
            "is_unread": 1,
            "in_inbox": 1,
            "indexed_at": "2026-08-13T00:00:00+00:00",
        }
        columns = email_index.EMAIL_COLUMNS
        placeholders = ", ".join("?" for _ in columns)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                f"INSERT INTO emails ({', '.join(columns)}) VALUES ({placeholders})",
                [row[column] for column in columns],
            )
            conn.commit()

    def test_init_db_creates_schema(self):
        email_index.init_db(self.db_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        self.assertIn("emails", tables)

    def test_insert_one_email(self):
        email_index.upsert_email(
            fake_mail("m1", "一般通知", "Sender <sender@example.com>"),
            self.db_path,
        )

        self.assertEqual(self.count_rows(), 1)

    def test_upsert_same_message_keeps_one_row(self):
        email_index.upsert_email(
            fake_mail("m1", "一般通知", "Sender <sender@example.com>"),
            self.db_path,
        )
        email_index.upsert_email(
            fake_mail("m1", "更新後的一般通知", "Sender <sender@example.com>"),
            self.db_path,
        )

        self.assertEqual(self.count_rows(), 1)

    def test_upsert_refreshes_existing_classification_fields(self):
        self.insert_stale_student_loan_bill_row("student-loan-1")

        email_index.upsert_email(
            fake_mail(
                "student-loan-1",
                "就學貸款撥款通知",
                "台北富邦銀行 <notice@fubon.com>",
                snippet="內容含電子帳單、帳單、繳款、應繳",
                importance={
                    "score": 75,
                    "level": "mid",
                    "tags": [],
                    "can_archive": False,
                },
            ),
            self.db_path,
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            stored = conn.execute(
                """
                SELECT category_label, bank_name, finance_type
                FROM emails
                WHERE message_id = ?
                """,
                ("student-loan-1",),
            ).fetchone()

        self.assertEqual(
            stored,
            ("AI/金融/富邦/一般通知", "富邦", "一般通知"),
        )
        self.assertEqual(self.count_rows(), 1)

    def test_sync_refreshes_existing_classification_fields(self):
        self.insert_stale_student_loan_bill_row("student-loan-production")
        mail = fake_mail(
            "student-loan-production",
            "就學貸款撥款通知",
            "台北富邦銀行 <notice@fubon.com>",
            snippet="內容含電子帳單、帳單、繳款、應繳",
            importance={
                "score": 75,
                "level": "mid",
                "tags": [],
                "can_archive": False,
            },
        )

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher([mail]),
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            stored = conn.execute(
                """
                SELECT subject, category_label, bank_name, finance_type
                FROM emails
                WHERE message_id = ?
                """,
                ("student-loan-production",),
            ).fetchone()

        self.assertEqual(stats["updated"], 1)
        self.assertEqual(
            stored,
            (
                "就學貸款撥款通知",
                "AI/金融/富邦/一般通知",
                "富邦",
                "一般通知",
            ),
        )
        self.assertEqual(self.count_rows(), 1)

    def test_debug_message_refreshes_classification_from_fake_gmail(self):
        self.insert_stale_student_loan_bill_row("student-loan-debug")
        service = FakeGmailService(
            {
                "student-loan-debug": fake_gmail_metadata(
                    "student-loan-debug",
                    "就學貸款撥款通知",
                    "台北富邦銀行 <notice@fubon.com>",
                    "內容含電子帳單、帳單、繳款、應繳",
                )
            }
        )
        output = io.StringIO()

        result = email_index.debug_message(
            "student-loan-debug",
            db_path=self.db_path,
            service=service,
            stream=output,
        )

        self.assertEqual(
            result["classification"]["label"],
            "AI/金融/富邦/一般通知",
        )
        self.assertEqual(result["db"]["category_label"], "AI/金融/富邦/一般通知")
        self.assertEqual(result["db"]["bank_name"], "富邦")
        self.assertEqual(result["db"]["finance_type"], "一般通知")
        self.assertEqual(self.count_rows(), 1)
        self.assertIn("Before UPSERT", output.getvalue())
        self.assertIn("After UPSERT", output.getvalue())

    def test_debug_message_keeps_real_fubon_credit_card_bill(self):
        service = FakeGmailService(
            {
                "fubon-card-debug": fake_gmail_metadata(
                    "fubon-card-debug",
                    "台北富邦銀行2026年7月信用卡帳單",
                    "台北富邦銀行 <notice@fubon.com>",
                    "",
                )
            }
        )

        result = email_index.debug_message(
            "fubon-card-debug",
            db_path=self.db_path,
            service=service,
            stream=io.StringIO(),
        )

        self.assertEqual(result["classification"]["bank"], "富邦")
        self.assertEqual(result["classification"]["finance_type"], "帳單")
        self.assertEqual(result["db"]["finance_type"], "帳單")

    def test_upsert_updates_unread_and_inbox(self):
        email_index.upsert_email(
            fake_mail(
                "m1",
                "一般通知",
                "Sender <sender@example.com>",
                labels=["INBOX", "UNREAD"],
            ),
            self.db_path,
        )
        email_index.upsert_email(
            fake_mail(
                "m1",
                "一般通知",
                "Sender <sender@example.com>",
                labels=[],
            ),
            self.db_path,
        )

        rows = email_index.get_recent_emails(limit=1, days=1, db_path=self.db_path)
        self.assertFalse(rows[0]["is_unread"])
        self.assertFalse(rows[0]["in_inbox"])

    def test_bank_statement_query(self):
        email_index.upsert_email(
            fake_mail(
                "tcb-bill",
                "合作金庫電子對帳單",
                "合作金庫銀行 <service@tcb-bank.com.tw>",
            ),
            self.db_path,
        )

        rows = email_index.get_bank_statements(
            bank_name="合作金庫",
            db_path=self.db_path,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bank_name"], "合作金庫")
        self.assertEqual(rows[0]["finance_type"], "帳單")

    def test_bank_login_query(self):
        email_index.upsert_email(
            fake_mail(
                "ctbc-login",
                "中國信託登入成功通知",
                "中國信託 <notice@ctbcbank.com>",
            ),
            self.db_path,
        )

        rows = email_index.get_login_records(
            bank_name="中國信託",
            bank_only=True,
            db_path=self.db_path,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bank_name"], "中國信託")
        self.assertEqual(rows[0]["finance_type"], "登入紀錄")

    def test_security_email_query(self):
        email_index.upsert_email(
            fake_mail(
                "luma-passkey",
                "Luma Passkey 安全通知",
                "Luma <hello@luma.com>",
            ),
            self.db_path,
        )

        rows = email_index.get_security_emails(db_path=self.db_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["security_type"], "Passkey")

    def test_important_email_query_uses_score(self):
        email_index.upsert_email(
            fake_mail(
                "important",
                "重要通知",
                "Sender <sender@example.com>",
                importance={
                    "score": 95,
                    "level": "高重要",
                    "tags": ["重要"],
                    "can_archive": False,
                },
            ),
            self.db_path,
        )

        rows = email_index.get_important_emails(db_path=self.db_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["importance_score"], 95)

    def test_date_range_filter(self):
        old_date = NOW - timedelta(days=40)
        new_date = NOW - timedelta(days=5)
        email_index.upsert_email(
            fake_mail(
                "old-bill",
                "合作金庫電子對帳單",
                "合作金庫銀行 <service@tcb-bank.com.tw>",
                internal_date=old_date,
            ),
            self.db_path,
        )
        email_index.upsert_email(
            fake_mail(
                "new-bill",
                "合作金庫電子對帳單",
                "合作金庫銀行 <service@tcb-bank.com.tw>",
                internal_date=new_date,
            ),
            self.db_path,
        )

        rows = email_index.get_bank_statements(
            date_from=(NOW - timedelta(days=10)).date().isoformat(),
            date_to=NOW.date().isoformat(),
            db_path=self.db_path,
        )

        self.assertEqual([row["message_id"] for row in rows], ["new-bill"])

    def test_progress_with_zero_emails_does_not_divide_by_zero(self):
        output = io.StringIO()

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher([]),
            progress=True,
            stream=output,
        )

        self.assertEqual(stats["fetched"], 0)
        self.assertEqual(stats["processed"], 0)
        self.assertIn("找到 0 封", output.getvalue())

    def test_progress_with_one_email_reaches_100_percent(self):
        output = io.StringIO()

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher(
                [fake_mail("progress-1", "Progress one", "Sender <s@example.com>")]
            ),
            progress=True,
            stream=output,
        )

        self.assertEqual(stats["processed"], 1)
        self.assertIn("100% 1/1", output.getvalue())

    def test_progress_with_100_emails_reaches_100_percent(self):
        output = io.StringIO()
        emails = [
            fake_mail(f"progress-{i}", f"Progress {i}", "Sender <s@example.com>")
            for i in range(100)
        ]

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher(emails),
            progress=True,
            stream=output,
        )

        self.assertEqual(stats["processed"], 100)
        self.assertEqual(self.count_rows(), 100)
        self.assertIn("100% 100/100", output.getvalue())

    def test_single_email_failure_continues(self):
        output = io.StringIO()
        emails = [
            fake_mail("good-1", "Good one", "Sender <s@example.com>"),
            {"subject": "Missing id should fail"},
            fake_mail("good-2", "Good two", "Sender <s@example.com>"),
        ]

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher(emails),
            progress=True,
            stream=output,
        )

        self.assertEqual(stats["errors"], 1)
        self.assertEqual(stats["processed"], 3)
        self.assertEqual(self.count_rows(), 2)
        self.assertIn("單封同步失敗：message_id=-", output.getvalue())

    def test_ctrl_c_keeps_completed_writes(self):
        output = io.StringIO()
        emails = [
            fake_mail("before-interrupt", "Before interrupt", "Sender <s@example.com>"),
            InterruptingMail(),
            fake_mail("after-interrupt", "After interrupt", "Sender <s@example.com>"),
        ]

        stats = email_index.sync_email_index(
            db_path=self.db_path,
            fetcher=fake_fetcher(emails),
            progress=True,
            stream=output,
        )

        self.assertTrue(stats["interrupted"])
        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["inserted"], 1)
        self.assertEqual(self.count_rows(), 1)

    def test_bank_statements_exclude_false_positive_finance_types(self):
        emails = [
            fake_mail(
                "line-bank-bill",
                "LINE Bank 電子對帳單",
                "LINE Bank <service@linebank.com.tw>",
            ),
            fake_mail(
                "cathay-statement",
                "國泰世華銀行綜合對帳單",
                "國泰世華 <notice@cathaybk.com.tw>",
            ),
            fake_mail(
                "tcb-statement",
                "合作金庫銀行電子綜合對帳單",
                "合作金庫銀行 <service@tcb-bank.com.tw>",
            ),
            fake_mail(
                "ctbc-statement",
                "中國信託銀行電子對帳單",
                "中國信託銀行 <notice@ctbcbank.com>",
            ),
            fake_mail(
                "fubon-card-bill",
                "台北富邦銀行信用卡帳單",
                "台北富邦銀行 <notice@fubon.com>",
            ),
            fake_mail(
                "fubon-card-bill-2026",
                "台北富邦銀行2026年7月信用卡帳單",
                "台北富邦銀行 <notice@fubon.com>",
            ),
            fake_mail(
                "fubon-bank-statement",
                "台北富邦銀行2026年7月 銀行對帳單",
                "台北富邦銀行 <notice@fubon.com>",
            ),
            fake_mail(
                "maicoin-promo",
                "MaiCoin｜LINE Bank 綁定扣款全新登場！買幣滿千送百",
                "LINE Bank <service@linebank.com.tw>",
            ),
            fake_mail(
                "link-success",
                "帳戶連結設定成功",
                "LINE Bank <service@linebank.com.tw>",
            ),
            fake_mail(
                "fubon-payment-promo",
                "繳費現賺2%回饋",
                "富邦銀行 <notice@fubon.com>",
            ),
            fake_mail(
                "cathay-card-notice",
                "簽帳金融卡電子消費通知書",
                "國泰世華 <notice@cathaybk.com.tw>",
            ),
            fake_mail(
                "fubon-bill-reminder",
                "提醒您本期信用卡帳單繳款截止日快到囉",
                "台北富邦銀行 <notice@fubon.com>",
                snippet="本期帳單繳款資訊請登入查詢。",
            ),
            fake_mail(
                "student-loan",
                "就學貸款撥款通知",
                "台北富邦銀行 <notice@fubon.com>",
                snippet="後續帳單與繳款資訊請留意通知。",
            ),
        ]

        for mail in emails:
            email_index.upsert_email(mail, self.db_path)

        rows = email_index.get_bank_statements(db_path=self.db_path)

        self.assertEqual(
            {row["message_id"] for row in rows},
            {
                "line-bank-bill",
                "cathay-statement",
                "tcb-statement",
                "ctbc-statement",
                "fubon-card-bill",
                "fubon-card-bill-2026",
                "fubon-bank-statement",
            },
        )
        fubon_rows = email_index.get_bank_emails(
            "富邦",
            limit=20,
            db_path=self.db_path,
        )
        loan_rows = [
            row for row in fubon_rows if row["message_id"] == "student-loan"
        ]
        self.assertEqual(loan_rows[0]["finance_type"], "一般通知")
        with closing(sqlite3.connect(self.db_path)) as conn:
            stored = conn.execute(
                """
                SELECT subject, category_label, bank_name, finance_type
                FROM emails
                WHERE message_id = ?
                """,
                ("student-loan",),
            ).fetchone()
        self.assertEqual(
            stored,
            (
                "就學貸款撥款通知",
                "AI/金融/富邦/一般通知",
                "富邦",
                "一般通知",
            ),
        )

    def test_bank_login_records_exclude_promos_and_transfers(self):
        emails = [
            fake_mail(
                "real-login",
                "中國信託 行動銀行APP登入成功通知",
                "中國信託銀行 <notice@ctbcbank.com>",
            ),
            fake_mail(
                "fubon-promo",
                "登入 Fubon+ 領券抽漢來",
                "富邦銀行 <notice@fubon.com>",
            ),
            fake_mail(
                "ctbc-transfer",
                "臺幣轉帳交易結果通知",
                "中國信託銀行 <notice@ctbcbank.com>",
                snippet="請登入網路銀行查詢交易明細",
            ),
            fake_mail(
                "ctbc-travel",
                "中信商旅鈦金卡旅遊優惠",
                "中國信託銀行 <notice@ctbcbank.com>",
            ),
        ]

        for mail in emails:
            email_index.upsert_email(mail, self.db_path)

        rows = email_index.get_login_records(
            bank_only=True,
            db_path=self.db_path,
        )

        self.assertEqual([row["message_id"] for row in rows], ["real-login"])

    def test_index_module_has_no_ai_dependency(self):
        source = (ROOT / "email_index.py").read_text(encoding="utf-8").lower()

        self.assertNotIn("openai", source)
        self.assertNotIn("ai_summary", source)
        self.assertNotIn("summarize_emails", source)


if __name__ == "__main__":
    unittest.main()
