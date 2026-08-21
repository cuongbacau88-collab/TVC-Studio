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

    def test_settlement_separates_service_credits_reward_x_and_money(self):
        request = request_json({}, "/api/admin/topups/1/approve")
        with patch.object(app, "require_admin", return_value=None):
            result = app.approve_topup(self.topup_id, request)
        self.assertEqual(2, result["buyer_bonus"])
        self.assertEqual(2000, result["direct_commission"])
        with patch.object(app, "require_admin", return_value=None), self.assertRaises(app.HTTPException) as raised:
            app.approve_topup(self.topup_id, request)
        self.assertEqual(409, raised.exception.status_code)
        con = app.db()
        buyer_credits = con.execute("SELECT credits FROM users WHERE id=?", (self.buyer_id,)).fetchone()["credits"]
        self.assertEqual(20, buyer_credits)
        rewards = con.execute("SELECT reward_type,amount_credits,status FROM affiliate_rewards WHERE topup_id=?", (self.topup_id,)).fetchall()
        self.assertEqual([("buyer_bonus", 2.0, "pending")], [(row["reward_type"], row["amount_credits"], row["status"]) for row in rewards])
        commissions = con.execute("SELECT commission_type,amount_vnd,status FROM affiliate_commissions WHERE topup_id=?", (self.topup_id,)).fetchall()
        self.assertEqual([("direct", 2000, "pending")], [(row["commission_type"], row["amount_vnd"], row["status"]) for row in commissions])
        con.close()

    def test_second_topup_does_not_create_second_buyer_bonus(self):
        with patch.object(app, "require_admin", return_value=None):
            app.approve_topup(self.topup_id, request_json({}, "/api/admin/topups/1/approve"))
            con = app.db()
            con.execute("INSERT INTO topups(user_id,package,amount_vnd,credits,status,created_at) VALUES(?,?,?,?,?,?)", (self.buyer_id, "Second", 20000, 20, "pending", app.now_iso()))
            second_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.commit(); con.close()
            app.approve_topup(second_id, request_json({}, "/api/admin/topups/2/approve"))
        con = app.db()
        self.assertEqual(1, con.execute("SELECT COUNT(*) FROM affiliate_rewards WHERE user_id=? AND reward_type='buyer_bonus'", (self.buyer_id,)).fetchone()[0])
        self.assertEqual(40, con.execute("SELECT credits FROM users WHERE id=?", (self.buyer_id,)).fetchone()["credits"])
        con.close()

    def test_approving_buyer_bonus_does_not_change_service_credits(self):
        with patch.object(app, "require_admin", return_value=None):
            app.approve_topup(self.topup_id, request_json({}, "/api/admin/topups/1/approve"))
        reward_id = app.db().execute("SELECT id FROM affiliate_rewards WHERE topup_id=?", (self.topup_id,)).fetchone()[0]
        with patch.object(app, "require_admin", return_value=None):
            result = asyncio.run(app.approve_affiliate_reward(reward_id, request_json({}, f"/api/admin/affiliate/rewards/{reward_id}/approve")))
        self.assertFalse(result["credited_to_service"])
        con = app.db()
        self.assertEqual(20, con.execute("SELECT credits FROM users WHERE id=?", (self.buyer_id,)).fetchone()["credits"])
        self.assertEqual(2, con.execute("SELECT delta FROM affiliate_reward_credit_ledger WHERE reward_id=?", (reward_id,)).fetchone()["delta"])
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
