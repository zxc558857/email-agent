from datetime import datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from query_parser import TAIPEI_TZ, parse_query


NOW = datetime(2026, 8, 14, 15, 30, tzinfo=TAIPEI_TZ)


class QueryParserTests(unittest.TestCase):
    def parse(self, text):
        return parse_query(text, now=NOW)

    def test_today_emails(self):
        parsed = self.parse("今天有什麼郵件")

        self.assertTrue(parsed.matched)
        self.assertEqual(parsed.intent, "today_emails")
        self.assertEqual(parsed.date_from.hour, 0)
        self.assertEqual(parsed.date_from.tzinfo, TAIPEI_TZ)

    def test_yesterday_general_emails(self):
        parsed = self.parse("昨天有哪些信")

        self.assertEqual(parsed.intent, "recent_emails")
        self.assertEqual(parsed.date_label, "昨天")
        self.assertEqual(parsed.date_from.day, 13)
        self.assertEqual(parsed.date_from.hour, 0)
        self.assertEqual(parsed.date_to.hour, 23)

    def test_this_week_important_emails(self):
        parsed = self.parse("這星期有哪些重要郵件")

        self.assertEqual(parsed.intent, "important_emails")
        self.assertEqual(parsed.min_importance, 80)
        self.assertEqual(parsed.date_label, "本週")
        self.assertEqual(parsed.date_from.day, 10)

    def test_this_month_bank_statements(self):
        parsed = self.parse("這個月有哪些銀行帳單")

        self.assertEqual(parsed.intent, "bank_statements")
        self.assertEqual(parsed.date_label, "本月")
        self.assertIsNone(parsed.bank)

    def test_tcb_recent_three_month_statements(self):
        parsed = self.parse("合作金庫最近三個月有哪些帳單")

        self.assertEqual(parsed.intent, "bank_statements")
        self.assertEqual(parsed.bank, "合作金庫")
        self.assertEqual(parsed.date_label, "最近3個月")

    def test_fubon_login_failure(self):
        parsed = self.parse("富邦最近有沒有登入失敗")

        self.assertEqual(parsed.intent, "login_records")
        self.assertEqual(parsed.bank, "富邦")
        self.assertEqual(parsed.status, "failure")

    def test_ctbc_this_week_login(self):
        parsed = self.parse("中國信託這星期有登入紀錄嗎")

        self.assertEqual(parsed.intent, "login_records")
        self.assertEqual(parsed.bank, "中國信託")
        self.assertEqual(parsed.date_label, "本週")

    def test_recent_bank_logins(self):
        parsed = self.parse("最近有哪些銀行登入")

        self.assertEqual(parsed.intent, "login_records")
        self.assertTrue(parsed.bank_only)

    def test_google_security(self):
        parsed = self.parse("最近 Google 有什麼安全通知")

        self.assertEqual(parsed.intent, "security_emails")
        self.assertEqual(parsed.keyword, "Google")

    def test_passkey_security(self):
        parsed = self.parse("最近有沒有 Passkey 通知")

        self.assertEqual(parsed.intent, "security_emails")
        self.assertEqual(parsed.keyword, "Passkey")

    def test_today_important_mail(self):
        parsed = self.parse("今天有哪些重要信")

        self.assertEqual(parsed.intent, "today_emails")
        self.assertEqual(parsed.min_importance, 80)

    def test_reply_required(self):
        parsed = self.parse("最近有沒有需要我回覆的信")

        self.assertEqual(parsed.intent, "reply_required")

    def test_action_required(self):
        parsed = self.parse("最近有哪些信需要我處理")

        self.assertEqual(parsed.intent, "action_required")

    def test_sender_104(self):
        parsed = self.parse("最近104有寄什麼給我")

        self.assertEqual(parsed.intent, "sender_search")
        self.assertEqual(parsed.keyword, "104")

    def test_sender_deepseek(self):
        parsed = self.parse("幫我找 DeepSeek 的郵件")

        self.assertEqual(parsed.intent, "sender_search")
        self.assertEqual(parsed.keyword, "DeepSeek")

    def test_keyword_passkey(self):
        parsed = self.parse("找有 Passkey 的信")

        self.assertEqual(parsed.intent, "keyword_search")
        self.assertEqual(parsed.keyword, "Passkey")

    def test_work_emails(self):
        parsed = self.parse("今天有哪些工作郵件")

        self.assertEqual(parsed.intent, "work_emails")
        self.assertEqual(parsed.category, "AI/工作%")

    def test_school_emails(self):
        parsed = self.parse("最近有哪些學校郵件")

        self.assertEqual(parsed.intent, "school_emails")
        self.assertEqual(parsed.category, "AI/學校%")

    def test_summary_command_is_protected(self):
        self.assertFalse(self.parse("整理").matched)

    def test_update_index_command_is_protected(self):
        self.assertFalse(self.parse("更新索引").matched)

    def test_unknown_text_is_not_guessed(self):
        self.assertFalse(self.parse("摰奇怪完全不明").matched)

    def test_parser_has_no_llm_dependency(self):
        source = (ROOT / "query_parser.py").read_text(encoding="utf-8").lower()

        self.assertNotIn("openai", source)
        self.assertNotIn("ai_summary", source)
        self.assertNotIn("summarize_emails", source)


if __name__ == "__main__":
    unittest.main()
