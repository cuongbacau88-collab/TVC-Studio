import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import app
from starlette.requests import Request


def request(path, cookies=None):
    parsed = urlsplit(path)
    headers = []
    if cookies:
        headers.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({"type": "http", "method": "GET", "path": parsed.path, "query_string": parsed.query.encode(), "headers": headers})


class ReferralFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.originals = {name: getattr(app, name) for name in ("BASE", "DATA", "UPLOADS", "OUTPUTS", "DB_PATH", "COOKIE_SECURE")}
        app.BASE = root
        app.DATA = root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.COOKIE_SECURE = False
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.init_db()
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)", ("ref@example.com", "Referrer", "x", 0, "user", app.now_iso()))
        user_id = con.execute("SELECT id FROM users WHERE email='ref@example.com'").fetchone()["id"]
        code = app.ensure_user_referral_code(con, user_id)
        con.commit()
        con.close()
        self.code = code

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        self.temp.cleanup()

    def test_valid_referral_sets_cookie_and_route_redirects_to_login(self):
        response = app.home(request(f"/?ref={self.code}"))
        self.assertIn("tvc_referral_code", response.headers.get("set-cookie", ""))
        with patch.object(app, "current_user", return_value=None):
            redirect = app.referral_page(request("/referral"))
        self.assertEqual("/app?return_to=%2Freferral#login", redirect.headers["location"])

    def test_invalid_referral_does_not_set_cookie(self):
        response = app.home(request("/?ref=invalid-code"))
        self.assertNotIn("tvc_referral_code", response.headers.get("set-cookie", ""))


if __name__ == "__main__":
    unittest.main()