import unittest

import app


class AffiliateCommissionAuditTests(unittest.TestCase):
    def test_cash_commission_uses_paid_amount(self):
        self.assertEqual(49900, app.affiliate_commission_vnd(499000, 0.10))
        self.assertEqual(74850, app.affiliate_commission_vnd(499000, 0.15))


if __name__ == "__main__":
    unittest.main()
