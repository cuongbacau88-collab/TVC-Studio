import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

import app


class AffiliateRiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.original = (app.BASE, app.DATA, app.DB_PATH)
        app.BASE, app.DATA, app.DB_PATH = root, root / "data", root / "data" / "test.db"
        app.DATA.mkdir(parents=True)
        app.init_db()

    def tearDown(self):
        app.BASE, app.DATA, app.DB_PATH = self.original
        self.temp.cleanup()

    def test_same_visitor_is_reported_without_mutating_affiliate_data(self):
        con = app.db()
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at,referral_code) VALUES(?,?,?,?,?,?,?)", ("referrer@example.com", "Referrer", "x", 10, "user", app.now_iso(), "refcode"))
        referrer_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO users(email,name,password_hash,credits,role,created_at,referred_by_user_id) VALUES(?,?,?,?,?,?,?)", ("referred@example.com", "Referred", "x", 20, "user", app.now_iso(), referrer_id))
        referred_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        for user_id in (referrer_id, referred_id):
            con.execute("INSERT INTO security_logs(created_at,event,severity,user_id,email,role,ip_address,user_agent,method,path,visitor_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (app.now_iso(), "google_login_success", "info", user_id, "referrer@example.com" if user_id == referrer_id else "referred@example.com", "user", "203.0.113.5", "Chrome/151 Windows", "GET", "/app", "v_same_browser"))
        con.commit()
        before = con.execute("SELECT credits,referred_by_user_id FROM users ORDER BY id").fetchall()
        con.close()

        request = Request({"type": "http", "method": "GET", "path": "/api/admin/affiliate/risk-reports", "query_string": b"", "headers": []})
        with patch.object(app, "require_admin", return_value=None):
            result = app.admin_affiliate_risk_reports(request)
        self.assertEqual(len(result["items"]), 1)
        self.assertGreaterEqual(result["items"][0]["risk_score"], 70)
        self.assertTrue(any("visitor_id" in reason for reason in result["items"][0]["reasons"]))
        con = app.db()
        after = con.execute("SELECT credits,referred_by_user_id FROM users ORDER BY id").fetchall()
        con.close()
        self.assertEqual([tuple(row) for row in before], [tuple(row) for row in after])


if __name__ == "__main__":
    unittest.main()
