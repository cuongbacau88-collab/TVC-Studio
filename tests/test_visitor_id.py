import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.responses import Response
from starlette.requests import Request

import app


def request_with_cookie(cookie=""):
    headers = [(b"user-agent", b"Mozilla/5.0 Test Browser")]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/app",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
    })


class VisitorIdTests(unittest.TestCase):
    def test_first_request_sets_cookie_and_next_request_reuses_it(self):
        async def endpoint(request):
            response = Response(request.state.visitor_id)
            return response

        first = asyncio.run(app.identify_visitor(request_with_cookie(), endpoint))
        cookie = first.headers["set-cookie"]
        visitor_id = first.body.decode()

        self.assertTrue(visitor_id.startswith("v_"))
        self.assertIn(f"{app.VISITOR_COOKIE}={visitor_id}", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)

        second = asyncio.run(app.identify_visitor(
            request_with_cookie(f"{app.VISITOR_COOKIE}={visitor_id}"), endpoint
        ))
        self.assertEqual(visitor_id, second.body.decode())
        self.assertNotIn("set-cookie", second.headers)

    def test_device_summary_keeps_two_visitors_on_same_ip_separate(self):
        temp = tempfile.TemporaryDirectory()
        original = (app.BASE, app.DATA, app.DB_PATH)
        try:
            root = Path(temp.name)
            app.BASE, app.DATA, app.DB_PATH = root, root / "data", root / "data" / "test.db"
            app.DATA.mkdir(parents=True)
            app.init_db()
            con = app.db()
            for visitor_id in ("v_visitor_a", "v_visitor_b"):
                con.execute(
                    "INSERT INTO admin_access_logs(ip_address,user_id,method,path,status_code,user_agent,created_at,visitor_id) VALUES(?,?,?,?,?,?,?,?)",
                    ("203.0.113.10", None, "GET", "/app", 200, "Safari iPhone", app.now_iso(), visitor_id),
                )
            con.commit()
            con.close()
            request = Request({"type": "http", "method": "GET", "path": "/api/admin/security-devices", "query_string": b"", "headers": []})
            with patch.object(app, "require_admin", return_value=None):
                rows = app.admin_security_devices(request)
            self.assertEqual({row["visitor_id"] for row in rows}, {"v_visitor_a", "v_visitor_b"})
        finally:
            app.BASE, app.DATA, app.DB_PATH = original
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
