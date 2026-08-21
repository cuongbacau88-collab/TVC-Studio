import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Response
from fastapi.responses import JSONResponse
from starlette.requests import Request

import app


def request_with_json(payload, headers=None):
    body=json.dumps(payload).encode("utf-8")
    sent=False

    async def receive():
        nonlocal sent
        if sent:
            return {"type":"http.disconnect"}
        sent=True
        return {"type":"http.request","body":body,"more_body":False}

    return Request({
        "type":"http",
        "method":"POST",
        "path":"/api/auth/google",
        "headers":[(b"content-type",b"application/json"), *(headers or [])],
    },receive)


class GoogleTestCreditsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.originals={
            "BASE":app.BASE,
            "DATA":app.DATA,
            "UPLOADS":app.UPLOADS,
            "OUTPUTS":app.OUTPUTS,
            "DB_PATH":app.DB_PATH,
            "TEST_MODE":app.TEST_MODE,
            "TEST_INITIAL_CREDITS":app.TEST_INITIAL_CREDITS,
            "COOKIE_SECURE":app.COOKIE_SECURE,
            "TRUST_PROXY":app.TRUST_PROXY,
        }
        app.BASE=self.root
        app.DATA=self.root/"data"
        app.UPLOADS=app.DATA/"uploads"
        app.OUTPUTS=app.DATA/"outputs"
        app.DB_PATH=app.DATA/"test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.COOKIE_SECURE=False
        app.TRUST_PROXY=True
        app.init_db()

    def tearDown(self):
        for name,value in self.originals.items():
            setattr(app,name,value)
        self.temp.cleanup()

    @staticmethod
    def google_info(account):
        return {
            "iss":"accounts.google.com",
            "aud":app.GOOGLE_CLIENT_ID,
            "email_verified":True,
            "sub":"google-"+account,
            "email":account+"@example.com",
            "name":"Account "+account,
            "picture":"",
        }

    def login(self,account):
        with patch.object(app.google_id_token,"verify_oauth2_token",return_value=self.google_info(account)):
            return asyncio.run(app.google_login(
                request_with_json({"credential":"server-verified-token"}),
                Response(),
            ))

    def credits(self,account):
        con=app.db()
        try:
            row=con.execute("SELECT credits FROM users WHERE email=?",(account+"@example.com",)).fetchone()
            return row["credits"] if row else None
        finally:
            con.close()

    def test_account_a_is_initialized_once_and_login_refresh_does_not_reset(self):
        app.TEST_MODE=True
        app.TEST_INITIAL_CREDITS=100

        first=self.login("a")
        self.assertTrue(first["new_user"])
        self.assertEqual(100,self.credits("a"))

        con=app.db()
        con.execute("UPDATE users SET credits=credits-1 WHERE email=?",("a@example.com",))
        con.commit()
        con.close()
        self.assertEqual(99,self.credits("a"))

        again=self.login("a")
        self.assertFalse(again["new_user"])
        self.assertEqual(99,self.credits("a"))

        again=self.login("a")
        self.assertEqual(99,self.credits("a"))
        con=app.db()
        ledger=con.execute(
            "SELECT COUNT(*) count FROM credit_ledger WHERE ref_type='test_google_signup'"
        ).fetchone()["count"]
        con.close()
        self.assertEqual(1,ledger)

    def test_account_b_gets_independent_initial_balance(self):
        app.TEST_MODE=True
        app.TEST_INITIAL_CREDITS=100
        self.login("a")
        self.login("b")
        self.assertEqual(100,self.credits("a"))
        self.assertEqual(100,self.credits("b"))

    def test_test_mode_false_never_grants_signup_credits(self):
        app.TEST_MODE=False
        app.TEST_INITIAL_CREDITS=100
        self.login("production")
        self.assertEqual(0,self.credits("production"))
        con=app.db()
        ledger=con.execute(
            "SELECT COUNT(*) count FROM credit_ledger WHERE ref_type='test_google_signup'"
        ).fetchone()["count"]
        con.close()
        self.assertEqual(0,ledger)

    def test_existing_google_balance_is_never_reset_when_config_changes(self):
        app.TEST_MODE=True
        app.TEST_INITIAL_CREDITS=100
        self.login("existing")
        con=app.db()
        con.execute("UPDATE users SET credits=37 WHERE email='existing@example.com'")
        con.commit()
        con.close()

        app.TEST_INITIAL_CREDITS=500
        self.login("existing")
        self.assertEqual(37,self.credits("existing"))

    def test_client_payload_cannot_choose_initial_credits(self):
        app.TEST_MODE=True
        app.TEST_INITIAL_CREDITS=100
        with patch.object(app.google_id_token,"verify_oauth2_token",return_value=self.google_info("client")):
            asyncio.run(app.google_login(
                request_with_json({
                    "credential":"server-verified-token",
                    "credits":999999,
                    "usage_balance":999999,
                }),
                Response(),
            ))
        self.assertEqual(100,self.credits("client"))

    def test_google_login_writes_security_log_without_token(self):
        request = request_with_json(
            {"credential":"server-verified-token"},
            [(b"cf-connecting-ip", b"14.170.119.29"), (b"user-agent", b"Test Mobile Chrome")],
        )
        with patch.object(app.google_id_token,"verify_oauth2_token",return_value=self.google_info("logged")):
            asyncio.run(app.google_login(request, Response()))
        con = app.db()
        rows = con.execute(
            "SELECT event,severity,email,ip_address,user_agent,metadata FROM security_logs ORDER BY id"
        ).fetchall()
        con.close()
        events = [row["event"] for row in rows]
        self.assertIn("google_login_success", events)
        self.assertIn("new_ip_login", events)
        success = next(row for row in rows if row["event"] == "google_login_success")
        self.assertEqual("14.170.119.29", success["ip_address"])
        self.assertEqual("Test Mobile Chrome", success["user_agent"])
        self.assertEqual("logged@example.com", success["email"])
        self.assertNotIn("server-verified-token", " ".join(str(row) for row in rows))

    def test_invalid_google_token_writes_security_log_and_creates_no_user(self):
        request = request_with_json(
            {"credential":"fake-token"},
            [(b"cf-connecting-ip", b"14.170.119.29"), (b"user-agent", b"curl")],
        )
        with patch.object(app.google_id_token,"verify_oauth2_token",side_effect=ValueError("invalid")):
            with self.assertRaises(app.HTTPException) as raised:
                asyncio.run(app.google_login(request, Response()))
        self.assertEqual(401, raised.exception.status_code)
        con = app.db()
        log = con.execute(
            "SELECT event,severity,ip_address,user_agent FROM security_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        users = con.execute("SELECT COUNT(*) AS count FROM users WHERE email='logged@example.com'").fetchone()["count"]
        con.close()
        self.assertEqual("google_token_invalid", log["event"])
        self.assertEqual("warning", log["severity"])
        self.assertEqual("14.170.119.29", log["ip_address"])
        self.assertEqual("curl", log["user_agent"])
        self.assertEqual(0, users)

    def test_admin_denied_request_creates_high_security_log(self):
        request = Request({
            "type": "http", "method": "GET", "path": "/api/admin/users",
            "headers": [(b"cf-connecting-ip", b"14.170.119.29"), (b"user-agent", b"curl")],
            "client": ("172.68.0.1", 443),
        })

        async def denied_endpoint(_request):
            return JSONResponse({"detail": "Không có quyền admin"}, status_code=403)

        response = asyncio.run(app.log_admin_access(request, denied_endpoint))
        self.assertEqual(403, response.status_code)
        con = app.db()
        log = con.execute(
            "SELECT event,severity,ip_address,path,http_status FROM security_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        self.assertEqual(("admin_access_denied", "high", "14.170.119.29", "/api/admin/users", 403), tuple(log))


if __name__=="__main__":
    unittest.main()
