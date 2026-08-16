import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Response
from starlette.requests import Request

import app


def request_with_json(payload):
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
        "headers":[(b"content-type",b"application/json")],
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
        }
        app.BASE=self.root
        app.DATA=self.root/"data"
        app.UPLOADS=app.DATA/"uploads"
        app.OUTPUTS=app.DATA/"outputs"
        app.DB_PATH=app.DATA/"test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.COOKIE_SECURE=False
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


if __name__=="__main__":
    unittest.main()
