from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mail_rules import needs_reply, score_email


def mail(subject, sender="Sender <sender@example.com>", snippet=""):
    return {
        "from": sender,
        "subject": subject,
        "snippet": snippet,
    }


class V24ImportanceTests(unittest.TestCase):
    def score(self, subject, sender="Sender <sender@example.com>", snippet=""):
        return score_email(mail(subject, sender, snippet))["score"]

    def test_fubon_survey_is_low_importance(self):
        score = self.score(
            "台北富邦銀行誠摯邀請您填寫 Fubon+ 調查問卷",
            "台北富邦銀行 <notice@fubon.com>",
        )

        self.assertLessEqual(score, 30)

    def test_fubon_coupon_login_promo_is_low_importance(self):
        score = self.score(
            "【限時快閃】登入 Fubon+ 領券抽餐券",
            "富邦銀行 <notice@fubon.com>",
        )

        self.assertLessEqual(score, 30)

    def test_codecademy_english_discount_is_low_importance(self):
        score = self.score(
            "50% off Pro ends tomorrow",
            "Codecademy <hello@codecademy.com>",
        )

        self.assertLessEqual(score, 30)

    def test_general_bank_promotion_is_low_importance(self):
        score = self.score(
            "信用卡優惠回饋活動",
            "台新銀行 <notice@taishin.com>",
        )

        self.assertLessEqual(score, 30)

    def test_books_coupon_notice_is_low_importance(self):
        score = self.score(
            "博客來單品折價券發放通知",
            "博客來 <notice@books.com.tw>",
            "折價券使用期限至明天。",
        )

        self.assertLessEqual(score, 30)

    def test_coupon_expiring_notice_is_low_importance(self):
        score = self.score("您的優惠券即將到期")

        self.assertLessEqual(score, 30)

    def test_shopping_credit_claim_notice_is_low_importance(self):
        score = self.score("限時領取 100 元購物金")

        self.assertLessEqual(score, 30)

    def test_payment_success_is_not_high_importance(self):
        score = self.score(
            "[OBgE TW] 付款狀態 更新為: 已付款",
            "OBgE TW <notice@example.com>",
            "如需變更密碼，請至會員中心設定。",
        )

        self.assertLess(score, 80)

    def test_payment_failure_is_high_importance(self):
        score = self.score("付款失敗通知", "Store <notice@example.com>")

        self.assertGreaterEqual(score, 80)

    def test_credit_card_transaction_failure_is_high_importance(self):
        score = self.score("信用卡交易失敗通知", "Bank <notice@example.com>")

        self.assertGreaterEqual(score, 80)

    def test_bank_login_success_is_medium_not_100(self):
        score = self.score(
            "中國信託 行動銀行APP登入成功通知",
            "中國信託銀行 <notice@ctbcbank.com>",
        )

        self.assertGreaterEqual(score, 40)
        self.assertLess(score, 80)
        self.assertNotEqual(score, 100)

    def test_quoted_bank_login_success_is_medium_not_high(self):
        score = self.score(
            "台北富邦行動銀行生物辨識登入「成功」通知",
            "台北富邦銀行 <notice@fubon.com>",
        )

        self.assertGreaterEqual(score, 50)
        self.assertLessEqual(score, 70)
        self.assertLess(score, 80)

    def test_bank_login_failure_is_high_importance(self):
        score = self.score(
            "中國信託 登入失敗通知",
            "中國信託銀行 <notice@ctbcbank.com>",
        )

        self.assertGreaterEqual(score, 80)

    def test_quoted_bank_login_failure_is_high_importance(self):
        score = self.score(
            "台北富邦行動銀行生物辨識登入「失敗」通知",
            "台北富邦銀行 <notice@fubon.com>",
        )

        self.assertGreaterEqual(score, 80)

    def test_bank_statement_is_medium_high(self):
        score = self.score(
            "合作金庫銀行115年7月份電子綜合對帳單",
            "合作金庫銀行 <service@tcb-bank.com.tw>",
        )

        self.assertGreaterEqual(score, 70)
        self.assertLessEqual(score, 90)

    def test_bank_e_statement_stays_medium_high(self):
        score = self.score("銀行電子對帳單", "Bank <notice@example.com>")

        self.assertGreaterEqual(score, 70)
        self.assertLessEqual(score, 90)

    def test_student_loan_approval_is_not_coupon_guarded(self):
        score = self.score(
            "就學貸款審核通過通知",
            "台北富邦銀行 <notice@fubon.com>",
        )

        self.assertGreaterEqual(score, 70)

    def test_student_loan_transaction_success_stays_important(self):
        score = self.score(
            "就學貸款續貸交易成功",
            "台北富邦銀行 <notice@fubon.com>",
        )

        self.assertGreaterEqual(score, 70)

    def test_google_security_alert_is_high_or_medium_high(self):
        score = self.score(
            "安全性快訊",
            "Google <no-reply@accounts.google.com>",
        )

        self.assertGreaterEqual(score, 70)

    def test_passkey_added_is_high_importance(self):
        score = self.score("新增 Passkey 至 Luma", "Luma <hello@luma.com>")

        self.assertGreaterEqual(score, 80)

    def test_third_party_access_is_high_importance(self):
        score = self.score(
            "您與 Claude 分享了部分 Google 帳戶資料",
            "Google <no-reply@accounts.google.com>",
        )

        self.assertGreaterEqual(score, 80)

    def test_samsung_new_product_ad_is_low_importance(self):
        score = self.score(
            "Samsung Galaxy 新品上市限時優惠",
            "Samsung <news@samsung.com>",
        )

        self.assertLessEqual(score, 30)

    def test_my104_job_recommendation_is_not_high_importance(self):
        score = self.score(
            "你關注的公司刊登新職務囉！",
            "My104會員中心 <mail@104.com.tw>",
        )

        self.assertGreaterEqual(score, 40)
        self.assertLess(score, 80)

    def test_interview_invitation_with_confirmation_is_high_importance(self):
        score = self.score(
            "面試邀請，請確認可面試時間",
            "Recruiter <hr@example.com>",
        )

        self.assertGreaterEqual(score, 80)

    def test_deepseek_pricing_announcement_does_not_need_reply(self):
        item = mail(
            "DeepSeek API pricing announcement",
            "DeepSeek <news@deepseek.com>",
        )

        self.assertFalse(needs_reply(item))

    def test_line_bank_investment_promo_does_not_need_reply(self):
        item = mail(
            "LINE Bank 投資優惠活動",
            "LINE Bank <service@linebank.com.tw>",
        )

        self.assertFalse(needs_reply(item))

    def test_clear_rsvp_request_needs_reply(self):
        item = mail(
            "請回覆是否參加下週會議",
            "Colleague <person@example.com>",
        )

        self.assertTrue(needs_reply(item))

    def test_provide_information_request_needs_reply(self):
        item = mail(
            "請提供以下資料",
            "HR <hr@example.com>",
        )

        self.assertTrue(needs_reply(item))

    def test_newsletter_does_not_need_reply(self):
        item = mail(
            "本週 newsletter",
            "News <news@example.com>",
        )

        self.assertFalse(needs_reply(item))


if __name__ == "__main__":
    unittest.main()
