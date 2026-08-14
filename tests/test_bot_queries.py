from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bot
import email_index


def fake_email(
    message_id,
    subject,
    sender="Sender <sender@example.com>",
    date="2026-08-14T05:20:00+00:00",
    bank_name=None,
    finance_type=None,
    security_type=None,
    category_label="AI/一般",
    importance_score=50,
):
    return {
        "message_id": message_id,
        "date": date,
        "sender": sender,
        "subject": subject,
        "bank_name": bank_name,
        "finance_type": finance_type,
        "security_type": security_type,
        "category_label": category_label,
        "importance_score": importance_score,
    }


class BotQueryTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.patches = [
            patch("bot.send_telegram_message", self.messages.append),
            patch("bot.is_email_index_available", return_value=True),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def joined_messages(self):
        return "\n".join(str(message) for message in self.messages)

    def test_today_email_queries_sqlite_and_not_ai(self):
        with patch.object(
            email_index,
            "get_emails",
            return_value=[
                fake_email(
                    "m1",
                    "安全性快訊",
                    "Google <no-reply@google.com>",
                    security_type="一般",
                    category_label="AI/安全/一般",
                    importance_score=90,
                )
            ],
        ) as get_emails, patch("bot.handle_summary_command") as summary:
            bot.handle_message("今日郵件")

        self.assertTrue(get_emails.called)
        kwargs = get_emails.call_args.kwargs
        self.assertEqual(kwargs["date_from"].tzinfo, bot.TAIPEI_TZ)
        self.assertEqual(kwargs["date_from"].hour, 0)
        self.assertFalse(summary.called)
        self.assertIn("今日郵件", self.joined_messages())
        self.assertIn("高重要：1", self.joined_messages())

    def test_recent_emails_show_latest_order_from_index(self):
        with patch.object(
            email_index,
            "get_recent_emails",
            return_value=[
                fake_email("new", "最新郵件", date="2026-08-14T05:20:00+00:00"),
                fake_email("old", "較舊郵件", date="2026-08-13T05:20:00+00:00"),
            ],
        ):
            bot.handle_message("最近郵件")

        output = self.joined_messages()
        self.assertLess(output.index("最新郵件"), output.index("較舊郵件"))

    def test_important_emails_use_importance_score(self):
        with patch.object(
            email_index,
            "get_important_emails",
            return_value=[fake_email("m1", "重要通知", importance_score=100)],
        ) as important:
            bot.handle_message("重要郵件")

        important.assert_called_once()
        self.assertIn("100分", self.joined_messages())

    def test_all_bank_statements_query(self):
        with patch.object(
            email_index,
            "get_bank_statements",
            return_value=[
                fake_email(
                    "m1",
                    "電子綜合對帳單",
                    bank_name="合作金庫",
                    finance_type="帳單",
                )
            ],
        ) as statements:
            bot.handle_message("銀行帳單")

        self.assertIsNone(statements.call_args.kwargs["bank_name"])
        self.assertIn("最近銀行帳單", self.joined_messages())
        self.assertIn("【合作金庫】", self.joined_messages())

    def test_tcb_statement_bank_name(self):
        with patch.object(email_index, "get_bank_statements", return_value=[]) as query:
            bot.handle_message("合作金庫帳單")

        self.assertEqual(query.call_args.kwargs["bank_name"], "合作金庫")

    def test_ctbc_alias_normalizes(self):
        self.assertEqual(bot.normalize_bank_name("中信帳單"), "中國信託")

    def test_cathay_alias_normalizes(self):
        self.assertEqual(bot.normalize_bank_name("國泰帳單"), "國泰世華")

    def test_linebank_alias_normalizes(self):
        self.assertEqual(bot.normalize_bank_name("LINEBank帳單"), "LINE Bank")

    def test_current_month_statement_uses_taipei_month_range(self):
        fixed_now = datetime(2026, 8, 14, 15, 30, tzinfo=bot.TAIPEI_TZ)
        with patch("bot.datetime") as fake_datetime, patch.object(
            email_index,
            "get_bank_statements",
            return_value=[],
        ) as query:
            fake_datetime.now.return_value = fixed_now
            fake_datetime.fromisoformat.side_effect = datetime.fromisoformat
            fake_datetime.fromtimestamp.side_effect = datetime.fromtimestamp
            bot.handle_message("本月帳單")

        kwargs = query.call_args.kwargs
        self.assertEqual(kwargs["date_from"].day, 1)
        self.assertEqual(kwargs["date_from"].hour, 0)
        self.assertEqual(kwargs["date_from"].tzinfo, bot.TAIPEI_TZ)
        self.assertEqual(kwargs["date_to"], fixed_now)

    def test_fubon_current_month_statement_combines_bank_and_range(self):
        with patch.object(email_index, "get_bank_statements", return_value=[]) as query:
            bot.handle_message("富邦本月帳單")

        self.assertEqual(query.call_args.kwargs["bank_name"], "富邦")
        self.assertIsNotNone(query.call_args.kwargs["date_from"])
        self.assertIsNotNone(query.call_args.kwargs["date_to"])

    def test_bank_login_sets_bank_only(self):
        with patch.object(email_index, "get_login_records", return_value=[]) as login:
            bot.handle_message("銀行登入")

        self.assertTrue(login.call_args.kwargs["bank_only"])

    def test_login_records_not_bank_only(self):
        with patch.object(email_index, "get_login_records", return_value=[]) as login:
            bot.handle_message("登入紀錄")

        self.assertFalse(login.call_args.kwargs["bank_only"])

    def test_ctbc_login_bank_name(self):
        with patch.object(email_index, "get_login_records", return_value=[]) as login:
            bot.handle_message("中國信託登入")

        self.assertEqual(login.call_args.kwargs["bank_name"], "中國信託")

    def test_security_notifications_query(self):
        with patch.object(email_index, "get_security_emails", return_value=[]) as security:
            bot.handle_message("安全通知")

        security.assert_called_once()
        self.assertIn("目前沒有找到安全通知", self.joined_messages())

    def test_update_index_syncs_recent_7_days(self):
        stats = {"fetched": 162, "inserted": 3, "updated": 159, "errors": 0}
        with patch.object(email_index, "sync_email_index", return_value=stats) as sync:
            bot.handle_message("更新索引")

        sync.assert_called_once_with(days=7, progress=False)
        self.assertIn("正在更新最近 7 天", self.joined_messages())
        self.assertIn("讀取：162", self.joined_messages())

    def test_query_commands_do_not_call_summary(self):
        commands = [
            "今日郵件",
            "最近郵件",
            "重要郵件",
            "銀行帳單",
            "富邦帳單",
            "登入紀錄",
            "銀行登入",
            "安全通知",
            "更新索引",
        ]
        with patch("bot.handle_summary_command") as summary, patch.object(
            email_index,
            "get_emails",
            return_value=[],
        ), patch.object(email_index, "get_recent_emails", return_value=[]), patch.object(
            email_index,
            "get_important_emails",
            return_value=[],
        ), patch.object(email_index, "get_bank_statements", return_value=[]), patch.object(
            email_index,
            "get_login_records",
            return_value=[],
        ), patch.object(email_index, "get_security_emails", return_value=[]), patch.object(
            email_index,
            "sync_email_index",
            return_value={"fetched": 0, "inserted": 0, "updated": 0, "errors": 0},
        ):
            for command in commands:
                bot.handle_message(command)

        self.assertFalse(summary.called)

    def test_summary_command_still_uses_original_summary_route(self):
        with patch("bot.run_summary") as run_summary:
            bot.handle_message("整理")

        run_summary.assert_called_once_with(show_loading=True)

    def test_label_command_still_uses_original_label_route(self):
        with patch("bot.handle_label_command") as label:
            bot.handle_message("分類")

        label.assert_called_once()

    def test_archive_command_still_uses_original_archive_route(self):
        with patch("bot.handle_archive_command") as archive:
            bot.handle_message("封存")

        archive.assert_called_once()

    def test_confirm_command_still_uses_original_confirm_route(self):
        with patch("bot.handle_confirm_command") as confirm:
            bot.handle_message("確認")

        confirm.assert_called_once()

    def test_missing_email_index_does_not_crash_or_query(self):
        with patch("bot.is_email_index_available", return_value=False), patch.object(
            email_index,
            "get_recent_emails",
        ) as recent:
            bot.handle_message("最近郵件")

        self.assertFalse(recent.called)
        self.assertIn("尚未建立郵件索引", self.joined_messages())

    def test_empty_result_has_clean_message(self):
        with patch.object(email_index, "get_bank_statements", return_value=[]):
            bot.handle_message("玉山帳單")

        output = self.joined_messages()
        self.assertIn("玉山銀行帳單", output)
        self.assertIn("目前索引中沒有找到符合條件的帳單", output)

    def test_large_results_are_limited_and_chunked_safely(self):
        rows = [
            fake_email(str(i), f"郵件 {i} " + "長主旨" * 40)
            for i in range(25)
        ]
        with patch.object(email_index, "get_recent_emails", return_value=rows):
            bot.handle_message("最近郵件")

        output = self.joined_messages()
        self.assertIn("另外還有 5 封未顯示", output)
        self.assertNotIn("郵件 24", output)
        self.assertTrue(all(len(message) <= bot.MESSAGE_SAFE_LIMIT for message in self.messages))

    def test_datetime_format_uses_taipei_timezone(self):
        text = bot.format_email_datetime(
            {"date": "2026-08-13T15:28:42+00:00"}
        )

        self.assertEqual(text, "08/13 23:28")

    def test_help_includes_v23_query_commands(self):
        bot.handle_message("幫助")

        output = self.joined_messages()
        self.assertIn("今日郵件", output)
        self.assertIn("銀行帳單", output)
        self.assertIn("更新索引", output)


if __name__ == "__main__":
    unittest.main()
