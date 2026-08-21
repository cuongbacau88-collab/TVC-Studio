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

    def test_withdrawal_reserves_and_conversion_cannot_reuse_it(self):
        with patch.object(app, "current_user", return_value=self.user()):
            result = asyncio.run(app.affiliate_request_withdrawal(request_json({"amount_vnd": 150000, "account_name": "Affiliate", "bank_name": "Bank", "account": "123", "method": "BANK"})))
            self.assertEqual(150000, result["amount_vnd"])
            with self.assertRaises(app.HTTPException):
                asyncio.run(app.affiliate_convert(request_json({"amount_vnd": 100000, "idempotency_key": "blocked"}, path="/api/affiliate/convert")))

    def test_conversion_keeps_decimal_and_idempotency(self):
        with patch.object(app, "current_user", return_value=self.user()):
            first = asyncio.run(app.affiliate_convert(request_json({"amount_vnd": 49900, "idempotency_key": "same"}, path="/api/affiliate/convert")))
            second = asyncio.run(app.affiliate_convert(request_json({"amount_vnd": 49900, "idempotency_key": "same"}, path="/api/affiliate/convert")))
        self.assertEqual(49.9, first["transaction"]["credits_received"])
        self.assertTrue(second["duplicate"])
        con = app.db(); self.assertEqual(49.9, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"]); con.close()

    def test_minimum_withdrawal_is_enforced(self):
        with patch.object(app, "current_user", return_value=self.user()):
            with self.assertRaises(app.HTTPException):
                asyncio.run(app.affiliate_request_withdrawal(request_json({"amount_vnd": 49999, "account_name": "Affiliate", "bank_name": "Bank", "account": "123", "method": "BANK"})))


if __name__ == "__main__":
    unittest.main()
