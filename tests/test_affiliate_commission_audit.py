import unittest

import app


class AffiliateCommissionAuditTests(unittest.TestCase):
    def test_cash_commission_uses_paid_amount(self):
        self.assertEqual(49900, app.affiliate_commission_vnd(499000, 0.10))
        self.assertEqual(74850, app.affiliate_commission_vnd(499000, 0.15))

    def test_internal_reward_conversion_preserves_existing_credit_payout(self):
        self.assertEqual(49.9, app.affiliate_commission_credits(499000, 0.10))
        self.assertEqual(74.85, app.affiliate_commission_credits(499000, 0.15))


if __name__ == "__main__":
    unittest.main()
