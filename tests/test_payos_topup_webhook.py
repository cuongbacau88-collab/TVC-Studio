import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

import app


def json_request(payload):
    body = json.dumps(payload).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({
        "type": "http", "method": "POST", "path": "/api/payos/webhook",
        "headers": [(b"content-type", b"application/json")],
    }, receive)


class PayOSTopupWebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH,
            "PAYOS_CLIENT_ID": app.PAYOS_CLIENT_ID,
            "PAYOS_API_KEY": app.PAYOS_API_KEY,
            "PAYOS_CHECKSUM_KEY": app.PAYOS_CHECKSUM_KEY,
        }
        app.BASE = root
        app.DATA = root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.PAYOS_CLIENT_ID = ""
        app.PAYOS_API_KEY = ""
        app.PAYOS_CHECKSUM_KEY = "test-checksum"
        app.init_db()
        con = app.db()
        con.execute(
            "INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)",
            ("buyer@example.com", "Buyer", "x", 10, "user", app.now_iso()),
        )
        self.user_id = con.execute(
            "SELECT id FROM users WHERE email='buyer@example.com'"
        ).fetchone()["id"]
        con.execute(
            """INSERT INTO topups(
                user_id,package,amount_vnd,credits,note,status,created_at,order_code,
                payment_link_id,checkout_url
            ) VALUES(?,?,?,?,?,'pending',?,?,?,?)""",
            (self.user_id, "creator", 199000, 220, "", app.now_iso(), 123456, "link-1", "https://payos.test"),
        )
        con.commit()
        con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        self.temp.cleanup()

    def payload(self, order_code=123456, amount=199000, payment_link_id="link-1", success=True):
        data = {
            "orderCode": order_code, "amount": amount,
            "paymentLinkId": payment_link_id, "reference": "ref-1",
            "code": "00", "success": success,
        }
        return {"code": "00", "success": success, "data": data,
                "signature": app.payos_signature(data)}

    def topup_state(self):
        con = app.db()
        try:
            topup = con.execute("SELECT status FROM topups WHERE order_code=123456").fetchone()
            user = con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()
            ledger = con.execute(
                "SELECT COUNT(*) count FROM credit_ledger WHERE ref_type='topup'"
            ).fetchone()
            return topup["status"], user["credits"], ledger["count"]
        finally:
            con.close()

    def test_success_credits_once_and_writes_ledger(self):
        first = asyncio.run(app.payos_webhook(json_request(self.payload())))
        second = asyncio.run(app.payos_webhook(json_request(self.payload())))
        self.assertTrue(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(("paid", 230, 1), self.topup_state())

    def test_create_link_persists_pending_before_payment_request(self):
        request = json_request({"package": "starter", "user_id": 999999})
        with patch.object(app, "current_user", return_value={"id": self.user_id}), \
                patch.object(app, "payos_create_payment", return_value={
                    "checkoutUrl": "https://payos.test/new", "paymentLinkId": "link-new"
                }):
            result = asyncio.run(app.create_payment_link(request))
        con = app.db()
        try:
            row = con.execute("SELECT * FROM topups WHERE id=?", (result["topup_id"],)).fetchone()
            self.assertEqual(self.user_id, row["user_id"])
            self.assertEqual("pending", row["status"])
            self.assertEqual("link-new", row["payment_link_id"])
        finally:
            con.close()

    def test_invalid_signature_does_not_credit(self):
        payload = self.payload()
        payload["signature"] = "bad"
        with self.assertRaises(HTTPException):
            asyncio.run(app.payos_webhook(json_request(payload)))
        self.assertEqual(("pending", 10, 0), self.topup_state())

    def test_amount_mismatch_is_review_only(self):
        result = asyncio.run(app.payos_webhook(json_request(self.payload(amount=1000))))
        self.assertTrue(result["success"])
        self.assertEqual(("pending", 10, 0), self.topup_state())
        con = app.db()
        self.assertEqual(1, con.execute(
            "SELECT needs_review FROM topups WHERE order_code=123456"
        ).fetchone()["needs_review"])
        con.close()

    def test_unknown_order_does_not_credit(self):
        result = asyncio.run(app.payos_webhook(json_request(self.payload(order_code=999999))))
        self.assertTrue(result["success"])
        self.assertEqual(("pending", 10, 0), self.topup_state())

    def test_admin_approve_after_auto_paid_cannot_credit_again(self):
        asyncio.run(app.payos_webhook(json_request(self.payload())))
        with patch.object(app, "require_admin", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                app.approve_topup(1, json_request({}))
        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(("paid", 230, 1), self.topup_state())

    def test_loading_admin_topups_does_not_settle_pending_payment(self):
        payment = {"status": "PAID", "amount": 199000, "reference": "ref-1", "payment_link_id": "link-1"}
        with patch.object(app, "require_admin", return_value=None), \
                patch.object(app, "payos_payment_status", return_value=payment) as status_check:
            rows = app.admin_topups(json_request({}))
        self.assertEqual("pending", rows[0]["status"])
        status_check.assert_not_called()
        self.assertEqual(("pending", 10, 0), self.topup_state())

    def test_admin_cannot_approve_unpaid_payos_topup(self):
        with patch.object(app, "require_admin", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                app.approve_topup(1, json_request({}))
        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual(("pending", 10, 0), self.topup_state())


if __name__ == "__main__":
    unittest.main()