import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import ai_summary


HEADINGS = [
    ai_summary.IMPORTANT_TITLE,
    ai_summary.REPLY_TITLE,
    ai_summary.PROMOTION_TITLE,
    ai_summary.ARCHIVE_TITLE,
]


def mail(
    subject,
    score,
    sender="Sender <sender@example.com>",
    snippet="",
    can_archive=False,
    message_id=None,
):
    item = {
        "from": sender,
        "subject": subject,
        "snippet": snippet,
        "importance": {
            "score": score,
            "level": "test-level",
            "can_archive": can_archive,
        },
    }
    if message_id:
        item["id"] = message_id
    return item


def section(output, heading):
    start = output.index(heading)
    next_starts = [
        output.index(candidate)
        for candidate in HEADINGS
        if candidate != heading and candidate in output and output.index(candidate) > start
    ]
    end = min(next_starts) if next_starts else len(output)
    return output[start:end]


class AiSummaryV243Tests(unittest.TestCase):
    def summarize_with_fake_ai(self, emails, summaries=None):
        payload = {
            "summaries": summaries
            or {
                str(index): {"summary": f"摘要 {index}", "action": ""}
                for index, _ in enumerate(emails, start=1)
            }
        }
        create = Mock(
            return_value=SimpleNamespace(
                output_text=json.dumps(payload, ensure_ascii=False)
            )
        )
        fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))

        with patch.object(ai_summary, "client", fake_client):
            output = ai_summary.summarize_emails(emails)

        return output, create

    def assert_not_important(self, output, subject):
        self.assertNotIn(subject, section(output, ai_summary.IMPORTANT_TITLE))

    def assert_important(self, output, subject):
        self.assertIn(subject, section(output, ai_summary.IMPORTANT_TITLE))

    def test_low_score_fubon_survey_is_not_important(self):
        subject = "Fubon+ 調查問卷"
        output, _ = self.summarize_with_fake_ai([mail(subject, 25)])

        self.assert_not_important(output, subject)

    def test_line_bank_investment_promo_is_not_important(self):
        subject = "LINE Bank 投資推廣"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 45, sender="LINE Bank <service@linebank.com.tw>")]
        )

        self.assert_not_important(output, subject)

    def test_deepseek_pricing_announcement_is_not_important(self):
        subject = "DeepSeek Pricing Announcement"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 45, sender="DeepSeek <news@deepseek.com>")]
        )

        self.assert_not_important(output, subject)

    def test_bank_statement_score_80_is_important(self):
        subject = "正式銀行對帳單"
        output, _ = self.summarize_with_fake_ai([mail(subject, 80)])

        self.assert_important(output, subject)

    def test_security_alert_score_90_is_important(self):
        subject = "安全性快訊"
        output, _ = self.summarize_with_fake_ai([mail(subject, 90)])

        self.assert_important(output, subject)

    def test_needs_reply_false_is_not_rendered_in_reply_section(self):
        subject = "DeepSeek API pricing announcement"
        output, _ = self.summarize_with_fake_ai([mail(subject, 45)])

        self.assertNotIn(subject, section(output, ai_summary.REPLY_TITLE))

    def test_needs_reply_true_is_rendered_in_reply_section(self):
        subject = "請回覆是否參加"
        output, _ = self.summarize_with_fake_ai([mail(subject, 45)])

        self.assertIn(subject, section(output, ai_summary.REPLY_TITLE))

    def test_can_archive_false_is_not_rendered_in_archive_section(self):
        subject = "帳戶安全通知"
        output, _ = self.summarize_with_fake_ai([mail(subject, 90, can_archive=False)])

        self.assertNotIn(subject, section(output, ai_summary.ARCHIVE_TITLE))

    def test_can_archive_true_low_risk_mail_is_rendered_in_archive_section(self):
        subject = "低風險電子報"
        output, _ = self.summarize_with_fake_ai([mail(subject, 60, can_archive=True)])

        self.assertIn(subject, section(output, ai_summary.ARCHIVE_TITLE))

    def test_empty_email_list_does_not_call_openai(self):
        create = Mock()
        fake_client = SimpleNamespace(responses=SimpleNamespace(create=create))

        with patch.object(ai_summary, "client", fake_client):
            output = ai_summary.summarize_emails([])

        self.assertIn("目前沒有未讀郵件", output)
        create.assert_not_called()

    def test_summary_uses_one_openai_call(self):
        emails = [
            mail("Fubon+ 調查問卷", 25),
            mail("安全性快訊", 90),
            mail("請回覆是否參加", 45),
        ]
        _, create = self.summarize_with_fake_ai(emails)

        create.assert_called_once()

    def test_ai_cannot_suggest_reply_or_archive_against_rules(self):
        subject = "LINE Bank 投資推廣"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 45, sender="LINE Bank <service@linebank.com.tw>")],
            {
                "1": {
                    "summary": "投資活動通知。",
                    "action": "請回覆並建議封存。",
                }
            },
        )

        self.assertNotIn("請回覆", output)
        self.assertNotIn("封存。", output)

    def test_promotion_with_can_archive_only_appears_in_promotion(self):
        subject = "Codecademy 50% off"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 25, can_archive=True)]
        )

        self.assertIn(subject, section(output, ai_summary.PROMOTION_TITLE))
        self.assertNotIn(subject, section(output, ai_summary.ARCHIVE_TITLE))
        self.assertEqual(output.count(subject), 1)

    def test_non_promotion_with_can_archive_appears_in_other_archive(self):
        subject = "低風險通知"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 60, can_archive=True)]
        )

        self.assertIn(subject, section(output, ai_summary.ARCHIVE_TITLE))
        self.assertNotIn(subject, section(output, ai_summary.PROMOTION_TITLE))

    def test_important_mail_only_appears_in_important_section(self):
        subject = "安全性快訊"
        output, _ = self.summarize_with_fake_ai(
            [mail(subject, 90, can_archive=True)]
        )

        self.assertIn(subject, section(output, ai_summary.IMPORTANT_TITLE))
        self.assertNotIn(subject, section(output, ai_summary.PROMOTION_TITLE))
        self.assertNotIn(subject, section(output, ai_summary.ARCHIVE_TITLE))
        self.assertEqual(output.count(subject), 1)

    def test_same_message_id_is_rendered_once_per_summary(self):
        subject = "LinkedIn 通知"
        output, _ = self.summarize_with_fake_ai(
            [
                mail(subject, 25, can_archive=True, message_id="same-message"),
                mail(subject, 25, can_archive=True, message_id="same-message"),
            ]
        )

        self.assertIn(subject, section(output, ai_summary.PROMOTION_TITLE))
        self.assertNotIn(subject, section(output, ai_summary.ARCHIVE_TITLE))
        self.assertEqual(output.count(subject), 1)


if __name__ == "__main__":
    unittest.main()
