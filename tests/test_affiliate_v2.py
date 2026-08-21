import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timezone
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

    return Request({
        "type": "http", "method": "POST", "path": path,
        "headers": [(b"content-type", b"application/json")],
    }, receive)


class AffiliateV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.original = (app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE)
        app.BASE, app.DATA, app.DB_PATH = root, root / "data", root / "data" / "test.db"
        app.UPLOADS, app.OUTPUTS, app.COOKIE_SECURE = app.DATA / "uploads", app.DATA / "outputs", False
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.init_db()
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("admin@example.com", "Admin", "x", 0, "admin", app.now_iso()))
        self.admin_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("affiliate@example.com", "Affiliate", "x", 0, "user", app.now_iso()))
        self.user_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("buyer@example.com", "Buyer", "x", 20, "user", app.now_iso()))
        self.buyer_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO topups(user_id,package,amount_vnd,credits,status,created_at) VALUES(?,?,?,?,?,?)", (self.buyer_id, "Test", 20000, 20, "paid", app.now_iso()))
        self.topup_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO affiliate_commissions(user_id,source_user_id,topup_id,commission_type,amount_vnd,rate,status,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.user_id, self.buyer_id, self.topup_id, "direct", 80000, 0.10, "approved", app.now_iso()))
        self.commission_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO affiliate_rewards(user_id,source_user_id,topup_id,reward_type,amount_credits,rate,status,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.buyer_id, self.buyer_id, self.topup_id, "buyer_bonus", 2, 0.10, "pending", app.now_iso()))
        self.reward_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit()
        con.close()

    def tearDown(self):
        app.BASE, app.DATA, app.UPLOADS, app.OUTPUTS, app.DB_PATH, app.COOKIE_SECURE = self.original
        self.temp.cleanup()

    def test_approved_money_paid_once_and_does_not_return_after_reload(self):
        actor = {"id": self.admin_id, "role": "admin", "email": "admin@example.com"}
        with patch.object(app, "require_admin", return_value=actor):
            result = asyncio.run(app.admin_affiliate_commission_paid(self.commission_id, request_json({}, "/api/admin/affiliate/commissions/1/paid")))
            self.assertEqual("paid", result["status"])
            with self.assertRaises(app.HTTPException) as raised:
                asyncio.run(app.admin_affiliate_commission_paid(self.commission_id, request_json({}, "/api/admin/affiliate/commissions/1/paid")))
        self.assertEqual(409, raised.exception.status_code)
        con = app.db()
        totals = app.affiliate_totals(con, self.user_id)
        self.assertEqual(0, totals["money_due_vnd"])
        self.assertEqual(80000, totals["money_paid_vnd"])
        con.close()
        con = app.db()
        totals_after_reload = app.affiliate_totals(con, self.user_id)
        self.assertEqual(totals, totals_after_reload)
        con.close()

    def test_pending_money_approval_is_idempotent(self):
        con = app.db()
        con.execute("UPDATE affiliate_commissions SET status='pending' WHERE id=?", (self.commission_id,))
        con.commit()
        con.close()
        actor = {"id": self.admin_id, "role": "admin", "email": "admin@example.com"}
        with patch.object(app, "require_admin", return_value=actor):
            result = asyncio.run(app.admin_affiliate_commission_approve(self.commission_id, request_json({}, "/api/admin/affiliate/commissions/1/approve")))
            self.assertEqual("approved", result["status"])
            with self.assertRaises(app.HTTPException) as raised:
                asyncio.run(app.admin_affiliate_commission_approve(self.commission_id, request_json({}, "/api/admin/affiliate/commissions/1/approve")))
        self.assertEqual(409, raised.exception.status_code)

    def test_reward_approval_is_separate_and_repeat_is_rejected(self):
        actor = {"id": self.admin_id, "role": "admin", "email": "admin@example.com"}
        with patch.object(app, "require_admin", return_value=actor):
            result = asyncio.run(app.approve_affiliate_reward(self.reward_id, request_json({}, "/api/admin/affiliate/rewards/1/approve")))
            self.assertFalse(result["credited_to_service"])
            with self.assertRaises(app.HTTPException) as raised:
                asyncio.run(app.approve_affiliate_reward(self.reward_id, request_json({}, "/api/admin/affiliate/rewards/1/approve")))
        self.assertEqual(409, raised.exception.status_code)
        con = app.db()
        self.assertEqual(20, con.execute("SELECT credits FROM users WHERE id=?", (self.buyer_id,)).fetchone()["credits"])
        self.assertEqual(2, con.execute("SELECT SUM(delta) FROM affiliate_reward_credit_ledger WHERE user_id=?", (self.buyer_id,)).fetchone()[0])
        con.close()

    def test_payout_date_is_day_25(self):
        self.assertEqual("2026-09-25", app.next_affiliate_payout_date(datetime(2026, 8, 26, tzinfo=timezone.utc)))
        self.assertEqual("2026-08-25", app.next_affiliate_payout_date(datetime(2026, 8, 24, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
