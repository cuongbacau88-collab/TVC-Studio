import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

import app


def request_json(payload, path):
    body = json.dumps(payload).encode()
    sent = False
    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}
    return Request({"type": "http", "method": "POST", "path": path, "headers": [(b"content-type", b"application/json")]}, receive)


class AffiliateBonusIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.original = (app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE)
        app.BASE, app.DATA, app.DB_PATH = root, root / "data", root / "data" / "test.db"
        app.UPLOADS, app.OUTPUTS, app.COOKIE_SECURE = app.DATA / "uploads", app.DATA / "outputs", False
        app.UPLOADS.mkdir(parents=True); app.OUTPUTS.mkdir(parents=True); app.init_db()
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at,referral_code) VALUES(?,?,?,?,?,?,?)", ("referrer@example.com", "Referrer", "x", 0, "user", app.now_iso(), "REF"))
        self.referrer_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at,referred_by_user_id) VALUES(?,?,?,?,?,?,?)", ("buyer@example.com", "Buyer", "x", 0, "user", app.now_iso(), self.referrer_id))
        self.buyer_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO topups(user_id,package,amount_vnd,credits,status,created_at) VALUES(?,?,?,?,?,?)", (self.buyer_id, "Test", 20000, 20, "pending", app.now_iso()))
        self.topup_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit(); con.close()

    def tearDown(self):
        app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE = self.original
        self.temp.cleanup()

    def user(self, user_id):
        return {"id": user_id, "role": "user", "email": "buyer@example.com" if user_id == self.buyer_id else "referrer@example.com"}

    def test_settlement_creates_bonus_and_direct_once(self):
        request = request_json({}, "/api/admin/topups/1/approve")
        with patch.object(app, "require_admin", return_value=None):
            result = app.approve_topup(self.topup_id, request)
        self.assertEqual(2, result["buyer_bonus"])
        self.assertEqual(2.0, result["direct_commission"])
        with patch.object(app, "require_admin", return_value=None), self.assertRaises(app.HTTPException) as raised:
            app.approve_topup(self.topup_id, request)
        self.assertEqual(409, raised.exception.status_code)
        con = app.db()
        rewards = con.execute("SELECT reward_type,amount_credits FROM affiliate_rewards WHERE topup_id=? ORDER BY reward_type", (self.topup_id,)).fetchall()
        self.assertEqual([("buyer_bonus", 2.0), ("direct", 2.0)], [(row["reward_type"], row["amount_credits"]) for row in rewards])
        con.close()

    def test_binding_never_creates_reward_and_cannot_rebind(self):
        con = app.db()
        con.execute("UPDATE users SET referred_by_user_id=NULL WHERE id=?", (self.buyer_id,))
        con.commit(); con.close()
        with patch.object(app, "current_user", return_value=self.user(self.buyer_id)):
            response = asyncio.run(app.affiliate_apply_code(request_json({"code": "REF"}, "/api/affiliate/apply-code")))
            self.assertEqual(0, response["rewards_created"])
            with self.assertRaises(app.HTTPException) as raised:
                asyncio.run(app.affiliate_apply_code(request_json({"code": "REF"}, "/api/affiliate/apply-code")))
            self.assertEqual(409, raised.exception.status_code)
        con = app.db()
        self.assertEqual(0, con.execute("SELECT COUNT(*) FROM affiliate_rewards WHERE user_id=?", (self.buyer_id,)).fetchone()[0])
        con.close()


if __name__ == "__main__":
    unittest.main()
