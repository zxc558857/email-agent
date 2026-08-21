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
    snippet="",
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
        "snippet": snippet,
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

    def test_natural_fubon_login_failure_uses_sqlite_and_not_ai(self):
        with patch.object(
            email_index,
            "get_login_records",
            return_value=[
                fake_email(
                    "login-failure",
                    "台北富邦行動銀行生物辨識登入「失敗」通知",
                    "台北富邦銀行 <notice@fubon.com>",
                    bank_name="富邦",
                    finance_type="登入紀錄",
                    importance_score=90,
                )
            ],
        ) as login, patch("bot.handle_summary_command") as summary:
            bot.handle_message("富邦最近有沒有登入失敗？")

        kwargs = login.call_args.kwargs
        self.assertEqual(kwargs["bank_name"], "富邦")
        self.assertEqual(kwargs["status"], "failure")
        self.assertFalse(summary.called)
        self.assertIn("富邦銀行登入紀錄", self.joined_messages())
        self.assertIn("失敗", self.joined_messages())

    def test_natural_reply_required_uses_needs_reply_and_not_ai(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email("reply", "請回覆是否參加會議", "HR <hr@example.com>"),
                fake_email("news", "本週 newsletter", "News <news@example.com>"),
            ],
        ) as search, patch("bot.handle_summary_command") as summary:
            bot.handle_message("最近有沒有需要我回覆的信")

        self.assertTrue(search.called)
        self.assertFalse(summary.called)
        output = self.joined_messages()
        self.assertIn("待回覆郵件", output)
        self.assertIn("請回覆是否參加會議", output)
        self.assertNotIn("newsletter", output)

    def test_natural_reply_required_uses_production_row_shape(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email(
                    "login-success",
                    "台北富邦行動銀行生物辨識登入「成功」通知",
                    "台北富邦行動銀行 <mbank@dfm.taipeifubon.com.tw>",
                    snippet="若非您本人操作，請確認帳戶安全。",
                    category_label="AI/金融/富邦/登入紀錄",
                    importance_score=60,
                ),
                fake_email(
                    "apple-pay",
                    "台北富邦銀行Apple Pay啟用通知",
                    "creditcard_center@fubon.com <creditcard_center@dfm.taipeifubon.com.tw>",
                    snippet="如非本人啟用，請確認裝置安全。",
                    category_label="AI/金融/富邦/信用卡",
                    importance_score=80,
                ),
                fake_email(
                    "system",
                    "一般系統通知",
                    "System <notice@example.com>",
                    snippet="請確認您的帳戶設定。",
                    category_label="AI/一般",
                    importance_score=50,
                ),
                fake_email(
                    "shopee-payment",
                    "蝦皮店到店代收款繳款證明",
                    '"蝦皮店到店" <stats.spx@shopee.com>',
                    snippet="請提供資料前，請確認交易內容。",
                    category_label="AI/購物",
                    importance_score=80,
                ),
                fake_email(
                    "meeting-reply",
                    "面試時間確認",
                    "HR <hr@example.com>",
                    snippet="請回覆是否可以參加週五面試。",
                    category_label="AI/工作",
                    importance_score=45,
                ),
            ],
        ):
            bot.handle_message("最近有沒有需要我回覆的信")

        output = self.joined_messages()
        self.assertIn("面試時間確認", output)
        self.assertNotIn("登入成功通知", output)
        self.assertNotIn("Apple Pay", output)
        self.assertNotIn("一般系統通知", output)
        self.assertNotIn("蝦皮店到店代收款繳款證明", output)

    def test_reply_required_formatter_receives_only_filtered_rows(self):
        rows = [
            fake_email(
                "login-success",
                "台北富邦行動銀行生物辨識登入「成功」通知",
                "台北富邦行動銀行 <mbank@dfm.taipeifubon.com.tw>",
                snippet="若非您本人操作，請確認帳戶安全。",
                category_label="AI/金融/富邦/登入紀錄",
                importance_score=60,
            ),
            fake_email(
                "reply",
                "出席確認",
                "Host <host@example.com>",
                snippet="請回覆是否參加。",
                importance_score=45,
            ),
        ]
        with patch.object(email_index, "search_emails", return_value=rows), patch(
            "bot.format_reply_required_emails",
            return_value="filtered",
        ) as formatter:
            bot.handle_message("最近有沒有需要我回覆的信")

        formatted_rows = formatter.call_args.args[0]
        self.assertEqual([row["message_id"] for row in formatted_rows], ["reply"])

    def test_reply_required_handler_keeps_only_production_ground_truth(self):
        rows = [
            fake_email(
                "seller-news",
                "🚀大促成功秘訣",
                '"蝦皮賣家報" <sellerinfo@newsletter.shopee.tw>',
                snippet="若有問題可回覆此信。",
            ),
            fake_email(
                "parking-confirm",
                "停車大聲公會員確認信",
                "停車大聲公團隊 <loudermama@parkinglotapp.com>",
                snippet="請點擊連結確認，若有問題可回覆此信。",
            ),
            fake_email(
                "patent-doc",
                "盧昱翰 先生3188--台灣發明「人工智慧聊天系統及其方法」中文專利說明書內容(ITW260372_P-3188-1)",
                "morris <morris@wpto.com.tw>",
                snippet="附件為專利說明書內容。",
            ),
            fake_email(
                "internship",
                "研揚科技-實習繳交資料說明",
                "VivianYuan 袁澄 <VivianYuan@aaeon.com.tw>",
                snippet="請回覆並提供實習繳交資料。",
            ),
            fake_email(
                "internship-re",
                "RE: 研揚科技-實習繳交資料說明",
                "VivianYuan 袁澄 <VivianYuan@aaeon.com.tw>",
                snippet="請回覆並提供實習繳交資料。",
            ),
        ]
        with patch.object(email_index, "search_emails", return_value=rows), patch(
            "bot.format_reply_required_emails",
            return_value="filtered",
        ) as formatter:
            bot.handle_message("最近有沒有需要我回覆的信")

        formatted_rows = formatter.call_args.args[0]
        self.assertEqual(
            [row["message_id"] for row in formatted_rows],
            ["internship", "internship-re"],
        )

    def test_natural_action_required_filters_score_or_reply_and_dedupes(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email(
                    "low-no-reply",
                    "台北富邦行動銀行生物辨識登入「成功」通知",
                    "台北富邦行動銀行 <mbank@dfm.taipeifubon.com.tw>",
                    snippet="若非您本人操作，請確認帳戶安全。",
                    category_label="AI/金融/富邦/登入紀錄",
                    importance_score=60,
                ),
                fake_email(
                    "high",
                    "重要通知",
                    "Security <security@example.com>",
                    importance_score=90,
                ),
                fake_email(
                    "reply",
                    "面試時間確認",
                    "HR <hr@example.com>",
                    snippet="請回覆是否可以參加週五面試。",
                    importance_score=45,
                ),
                fake_email(
                    "reply",
                    "面試時間確認",
                    "HR <hr@example.com>",
                    snippet="請回覆是否可以參加週五面試。",
                    importance_score=90,
                ),
            ],
        ):
            bot.handle_message("最近有沒有需要我處理的信")

        output = self.joined_messages()
        self.assertIn("需要處理的郵件", output)
        self.assertNotIn("登入成功通知", output)
        self.assertIn("重要通知", output)
        self.assertEqual(output.count("面試時間確認"), 1)

    def test_natural_deepseek_search_uses_sqlite_and_not_ai(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email(
                    "deepseek",
                    "Announcement on DeepSeek V4 API New Pricing",
                    "DeepSeek <news@deepseek.com>",
                )
            ],
        ) as search, patch("bot.handle_summary_command") as summary:
            bot.handle_message("幫我找 DeepSeek 的郵件")

        self.assertEqual(search.call_args.kwargs["sender"], "DeepSeek")
        self.assertFalse(summary.called)
        self.assertIn("DeepSeek 最近郵件", self.joined_messages())

    def test_natural_school_query_rechecks_stale_category_rows(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email(
                    "linkedin",
                    "👤 盧昱翰，去認識一下蘇彥宇",
                    "LinkedIn <messages-noreply@linkedin.com>",
                    snippet="國立政治大學的學生",
                    category_label="AI/學校",
                ),
                fake_email(
                    "school",
                    "開學選課通知",
                    "中國科技大學 教務處 <notice@example.edu.tw>",
                    snippet="請同學留意校務系統公告。",
                    category_label="AI/學校",
                    importance_score=80,
                ),
            ],
        ) as search:
            bot.handle_message("最近有哪些學校郵件")

        self.assertIsNone(search.call_args.kwargs["limit"])
        output = self.joined_messages()
        self.assertIn("學校郵件", output)
        self.assertIn("開學選課通知", output)
        self.assertNotIn("LinkedIn", output)

    def test_natural_work_query_rechecks_stale_category_rows(self):
        with patch.object(
            email_index,
            "search_emails",
            return_value=[
                fake_email(
                    "promo",
                    "限時購物優惠",
                    "Shop <shop@example.com>",
                    category_label="AI/工作",
                ),
                fake_email(
                    "work",
                    "面試時間確認",
                    "HR <hr@example.com>",
                    category_label="AI/工作",
                    importance_score=80,
                ),
            ],
        ):
            bot.handle_message("最近有哪些工作郵件")

        output = self.joined_messages()
        self.assertIn("工作郵件", output)
        self.assertIn("面試時間確認", output)
        self.assertNotIn("限時購物優惠", output)

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

    def test_rule_summary_v31_includes_important_and_reply_sections(self):
        emails = [
            fake_email(
                "important-reply",
                "Please reply with the requested information",
                "VivianYuan <VivianYuan@aaeon.com.tw>",
                importance_score=90,
            ),
            fake_email(
                "normal",
                "一般通知",
                "Notice <notice@example.com>",
                importance_score=50,
            ),
        ]

        message = bot.build_rule_summary_message(
            emails,
            [],
            datetime(2026, 8, 20, 8, 0, tzinfo=bot.TAIPEI_TZ),
        )

        self.assertIn("最近郵件：", message)
        self.assertIn("🔴 本次重要郵件", message)
        self.assertIn("1. 90分｜VivianYuan", message)
        self.assertIn("Please reply with the requested information", message)
        self.assertIn("📩 本次需要回覆", message)
        self.assertIn("1. VivianYuan", message)
        self.assertIn("自動整理使用規則，不使用 OpenAI API。", message)
        self.assertIn("若需要 AI 深度摘要，請輸入「整理」或 /summary。", message)
        self.assertLess(message.index("🔴 本次重要郵件"), message.index("📩 本次需要回覆"))
        self.assertLess(message.index("📩 本次需要回覆"), message.index("最近郵件："))

    def test_rule_summary_important_section_sorts_limits_and_dedupes(self):
        emails = [
            fake_email(
                "dup",
                "Duplicate Important",
                "VIP <vip@example.com>",
                date="2026-08-14T01:00:00+00:00",
                importance_score=100,
            ),
            fake_email(
                "dup",
                "Duplicate Important",
                "VIP <vip@example.com>",
                date="2026-08-14T01:00:00+00:00",
                importance_score=100,
            ),
            fake_email(
                "old90",
                "Older Ninety",
                "Old <old@example.com>",
                date="2026-08-13T01:00:00+00:00",
                importance_score=90,
            ),
            fake_email(
                "new90",
                "Newer Ninety",
                "New <new@example.com>",
                date="2026-08-14T02:00:00+00:00",
                importance_score=90,
            ),
            fake_email("m88", "Score Eighty Eight", importance_score=88),
            fake_email("m86", "Score Eighty Six", importance_score=86),
            fake_email("m84", "Score Eighty Four", importance_score=84),
            fake_email("m79", "Score Seventy Nine", importance_score=79),
        ]

        section = bot.format_rule_summary_important_emails(emails)

        self.assertEqual(section.count("Duplicate Important"), 1)
        self.assertLess(section.index("Newer Ninety"), section.index("Older Ninety"))
        self.assertIn("另外還有 1 封重要郵件。", section)
        self.assertNotIn("Score Eighty Four", section)
        self.assertNotIn("Score Seventy Nine", section)

    def test_rule_summary_empty_sections_use_clean_messages(self):
        section = "\n\n".join(
            [
                bot.format_rule_summary_important_emails([]),
                bot.format_rule_summary_reply_required_emails([]),
            ]
        )

        self.assertIn("本時段沒有高重要郵件。", section)
        self.assertIn("本時段沒有需要回覆的郵件。", section)

    def test_rule_summary_reply_section_uses_needs_reply_limits_and_dedupes(self):
        emails = [
            fake_email(
                "dup-reply",
                "Please reply with the requested information duplicate",
            ),
            fake_email(
                "dup-reply",
                "Please reply with the requested information duplicate",
            ),
        ] + [
            fake_email(
                f"reply-{i}",
                f"Please reply with the requested information {i}",
            )
            for i in range(6)
        ]

        section = bot.format_rule_summary_reply_required_emails(emails)

        self.assertEqual(section.count("requested information duplicate"), 1)
        self.assertIn("另外還有 2 封需要回覆的郵件。", section)

    def test_run_rule_summary_uses_current_processed_emails_for_v31_sections(self):
        current_emails = [
            {
                **fake_email(
                    "current-high",
                    "Current high rule score",
                    "Rules <rules@example.com>",
                    importance_score=None,
                ),
                "importance": {"score": 88, "level": "高", "can_archive": False},
            }
        ]

        with patch("bot.get_unread_emails", return_value=current_emails) as unread, patch(
            "bot.auto_label_emails",
            return_value=[],
        ) as auto_label:
            bot.run_rule_summary()

        unread.assert_called_once_with(limit=bot.AUTO_EMAIL_LIMIT)
        auto_label.assert_called_once()
        output = self.joined_messages()
        self.assertIn("Current high rule score", output)
        self.assertIn("88分｜Rules", output)

    def test_auto_summary_production_path_sends_v31_sections(self):
        emails = [
            {
                **fake_email(
                    "important",
                    "Production important subject",
                    "Important Sender <important@example.com>",
                    importance_score=90,
                ),
                "importance": {"score": 90, "level": "高", "can_archive": False},
            },
            {
                **fake_email(
                    "normal",
                    "Production normal subject",
                    "Normal Sender <normal@example.com>",
                    importance_score=45,
                ),
                "importance": {"score": 45, "level": "低", "can_archive": False},
            },
            {
                **fake_email(
                    "reply",
                    "Please reply with the requested information",
                    "Reply Sender <reply@example.com>",
                    importance_score=45,
                ),
                "importance": {"score": 45, "level": "低", "can_archive": False},
            },
        ]

        with patch("bot.get_unread_emails", return_value=emails) as unread, patch(
            "bot.auto_label_emails",
            return_value=[{"subject": mail["subject"], "label": "AI/一般"} for mail in emails],
        ), patch("bot.save_state") as save_state, patch("bot.run_summary") as ai_summary:
            state = {}
            bot.run_auto_summary("2026-08-20-21", state)

        unread.assert_called_once_with(limit=bot.AUTO_EMAIL_LIMIT)
        self.assertGreaterEqual(save_state.call_count, 2)
        self.assertFalse(ai_summary.called)
        self.assertEqual(len(self.messages), 1)

        sent = self.messages[0]
        self.assertIn("📬 郵件規則整理完成", sent)
        self.assertIn("🔴 本次重要郵件", sent)
        self.assertIn("90分", sent)
        self.assertIn("Production important subject", sent)
        self.assertIn("📩 本次需要回覆", sent)
        self.assertIn("Please reply with the requested information", sent)
        self.assertLess(sent.index("分類統計："), sent.index("🔴 本次重要郵件"))
        self.assertLess(sent.index("🔴 本次重要郵件"), sent.index("📩 本次需要回覆"))
        self.assertLess(sent.index("📩 本次需要回覆"), sent.index("最近郵件："))
        self.assertLess(sent.index("最近郵件："), sent.index("自動整理使用規則"))

    def test_auto_summary_production_path_renders_empty_v31_sections(self):
        emails = [
            {
                **fake_email(
                    "normal",
                    "DeepSeek API pricing announcement",
                    "DeepSeek <news@deepseek.com>",
                    importance_score=45,
                ),
                "importance": {"score": 45, "level": "低", "can_archive": False},
            }
        ]

        with patch("bot.get_unread_emails", return_value=emails), patch(
            "bot.auto_label_emails",
            return_value=[],
        ), patch("bot.save_state"), patch("bot.run_summary") as ai_summary:
            bot.run_auto_summary("2026-08-20-21", {})

        self.assertFalse(ai_summary.called)
        self.assertEqual(len(self.messages), 1)
        sent = self.messages[0]
        self.assertIn("🔴 本次重要郵件", sent)
        self.assertIn("本時段沒有高重要郵件。", sent)
        self.assertIn("📩 本次需要回覆", sent)
        self.assertIn("本時段沒有需要回覆的郵件。", sent)

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
