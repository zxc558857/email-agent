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

    def test_shopee_payment_certificate_does_not_need_reply(self):
        item = mail(
            "蝦皮店到店代收款繳款證明",
            '"蝦皮店到店" <stats.spx@shopee.com>',
            "請提供資料前，請確認交易內容。",
        )

        self.assertFalse(needs_reply(item))

    def test_payment_success_confirmation_does_not_need_reply(self):
        item = mail(
            "付款成功通知",
            "Store <notice@example.com>",
            "請確認交易內容。",
        )

        self.assertFalse(needs_reply(item))

    def test_receipt_confirmation_does_not_need_reply(self):
        item = mail(
            "電子收據",
            "Store <receipt@example.com>",
            "請確認資料。",
        )

        self.assertFalse(needs_reply(item))

    def test_confirm_and_reply_needs_reply(self):
        item = mail(
            "請確認並回覆是否出席",
            "Colleague <person@example.com>",
        )

        self.assertTrue(needs_reply(item))

    def test_english_requested_information_needs_reply(self):
        item = mail(
            "Please reply with the requested information",
            "HR <hr@example.com>",
        )

        self.assertTrue(needs_reply(item))

    def test_login_success_footer_confirmation_does_not_need_reply(self):
        item = mail(
            "台北富邦行動銀行生物辨識登入「成功」通知",
            "台北富邦行動銀行 <mbank@dfm.taipeifubon.com.tw>",
            "若非您本人操作，請確認帳戶安全。",
        )

        self.assertFalse(needs_reply(item))

    def test_aaeon_internship_materials_needs_reply(self):
        item = mail(
            "研揚科技-實習繳交資料說明",
            "VivianYuan 袁澄 <VivianYuan@aaeon.com.tw>",
            "請回覆並提供實習繳交資料。",
        )

        self.assertTrue(needs_reply(item))

    def test_aaeon_internship_reply_needs_reply(self):
        item = mail(
            "RE: 研揚科技-實習繳交資料說明",
            "VivianYuan 袁澄 <VivianYuan@aaeon.com.tw>",
            "請回覆並提供實習繳交資料。",
        )

        self.assertTrue(needs_reply(item))

    def test_seller_newsletter_reply_footer_does_not_need_reply(self):
        item = mail(
            "🚀大促成功秘訣",
            '"蝦皮賣家報" <sellerinfo@newsletter.shopee.tw>',
            "若有問題可回覆此信。",
        )

        self.assertFalse(needs_reply(item))

    def test_membership_confirmation_does_not_need_reply(self):
        item = mail(
            "停車大聲公會員確認信",
            "停車大聲公團隊 <loudermama@parkinglotapp.com>",
            "請點擊連結確認，若有問題可回覆此信。",
        )

        self.assertFalse(needs_reply(item))

    def test_patent_document_content_does_not_need_reply(self):
        item = mail(
            "盧昱翰 先生3188--台灣發明「人工智慧聊天系統及其方法」中文專利說明書內容(ITW260372_P-3188-1)",
            "morris <morris@wpto.com.tw>",
            "附件為專利說明書內容。",
        )

        self.assertFalse(needs_reply(item))

    def test_member_confirmation_click_link_does_not_need_reply(self):
        item = mail(
            "會員確認信",
            "Service <notice@example.com>",
            "請點擊連結確認。",
        )

        self.assertFalse(needs_reply(item))

    def test_newsletter_does_not_need_reply(self):
        item = mail(
            "本週 newsletter",
            "News <news@example.com>",
        )

        self.assertFalse(needs_reply(item))


if __name__ == "__main__":
    unittest.main()
