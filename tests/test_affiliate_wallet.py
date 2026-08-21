import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Response
from starlette.requests import Request

import app


def request_json(payload, method="POST", path="/api/affiliate/withdrawals"):
    body = json.dumps(payload).encode()
    sent = False
    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}
    return Request({"type": "http", "method": method, "path": path, "headers": [(b"content-type", b"application/json")]}, receive)


class AffiliateWalletTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.original = (app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE)
        app.BASE, app.DATA, app.DB_PATH = root, root / "data", root / "data" / "test.db"
        app.UPLOADS, app.OUTPUTS, app.COOKIE_SECURE = app.DATA / "uploads", app.DATA / "outputs", False
        app.UPLOADS.mkdir(parents=True); app.OUTPUTS.mkdir(parents=True); app.init_db()
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("affiliate@example.com", "Affiliate", "x", 0, "user", app.now_iso()))
        self.user_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("source@example.com", "Source", "x", 0, "user", app.now_iso()))
        source_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO topups(user_id,package,amount_vnd,credits,status,created_at) VALUES(?,?,?,?,?,?)", (source_id, "Test", 100000, 200, "paid", app.now_iso()))
        topup_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO affiliate_rewards(user_id,source_user_id,topup_id,reward_type,amount_credits,rate,status,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.user_id, source_id, topup_id, "direct", 200, .1, "approved", app.now_iso()))
        con.commit(); con.close()

    def tearDown(self):
        app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE = self.original
        self.temp.cleanup()

    def user(self):
        return {"id": self.user_id, "role": "user", "email": "affiliate@example.com"}

    def test_legacy_withdrawal_and_conversion_are_disabled(self):
        with patch.object(app, "current_user", return_value=self.user()):
            with self.assertRaises(app.HTTPException) as withdrawal:
                asyncio.run(app.affiliate_request_withdrawal(request_json({"amount_vnd": 150000})))
            with self.assertRaises(app.HTTPException) as conversion:
                asyncio.run(app.affiliate_convert(request_json({"amount_vnd": 100000, "idempotency_key": "blocked"}, path="/api/affiliate/convert")))
        self.assertEqual(410, withdrawal.exception.status_code)
        self.assertEqual(410, conversion.exception.status_code)

    def test_zero_balance_rejects_withdrawal_and_conversion(self):
        con = app.db()
        con.execute("UPDATE users SET credits=0 WHERE id=?", (self.user_id,))
        con.execute("DELETE FROM affiliate_rewards WHERE user_id=?", (self.user_id,))
        con.execute("DELETE FROM affiliate_withdrawals WHERE user_id=?", (self.user_id,))
        con.execute("DELETE FROM affiliate_wallet_transactions WHERE user_id=?", (self.user_id,))
        con.commit(); con.close()
        with patch.object(app, "current_user", return_value=self.user()):
            with self.assertRaises(app.HTTPException) as withdrawal:
                asyncio.run(app.affiliate_request_withdrawal(request_json({"amount_vnd": 50000})))
            with self.assertRaises(app.HTTPException) as conversion:
                asyncio.run(app.affiliate_convert(request_json({"amount_vnd": 50000, "idempotency_key": "zero"}, path="/api/affiliate/convert")))
        self.assertEqual(410, withdrawal.exception.status_code)
        self.assertEqual(410, conversion.exception.status_code)

    def test_referral_ui_zero_balance_and_minimum_messages(self):
        js = Path("static/referral-functions.js").read_text()
        self.assertNotIn("affiliateWithdrawBtn", js)
        self.assertNotIn("affiliateConvertBtn", js)
        self.assertIn("affiliateMoneyApproved", Path("static/app.html").read_text())
        self.assertIn("zalo.me/0867863222", Path("static/app.html").read_text())


if __name__ == "__main__":
    unittest.main()
