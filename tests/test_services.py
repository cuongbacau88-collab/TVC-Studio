import asyncio
import io
import os
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest

from fastapi import UploadFile
from starlette.requests import Request

import app
import service_routes
from service_worker_adapters import normalize_status, WorkerAdapterError
from storage_backend import LocalStorage


class Config:
    def __init__(self, configured=True):
        self.configured = configured


class FakeAdapter:
    def __init__(self, configured=True):
        self.config = Config(configured)
        self.submits = 0
        self.status_value = {"status": "queued", "progress": 0}
        self.cancelled = False

    def submit(self, client_job_id, payload, files):
        self.submits += 1
        return {"job_id": "worker-1", "status": "queued"}

    def status(self, worker_job_id):
        return self.status_value

    def cancel(self, worker_job_id):
        self.cancelled = True
        self.status_value = {"status": "cancelled", "progress": 100}
        return self.status_value

    def result(self, worker_job_id):
        raise AssertionError("not used")

    def health(self):
        return {"configured": self.config.configured, "online": self.config.configured}


class ServiceAPITests(unittest.TestCase):
    def setUp(self):
        self.original_outfit_model = os.environ.get("OUTFIT_MODEL")
        os.environ["OUTFIT_MODEL"] = "flux-2-klein-4b"
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.originals = {
            "BASE": app.BASE, "DATA": app.DATA, "UPLOADS": app.UPLOADS,
            "OUTPUTS": app.OUTPUTS, "DB_PATH": app.DB_PATH, "storage": app.storage,
            "service_adapters": app.service_adapters,
        }
        app.BASE = self.root
        app.DATA = self.root / "data"
        app.UPLOADS = app.DATA / "uploads"
        app.OUTPUTS = app.DATA / "outputs"
        app.DB_PATH = app.DATA / "test.db"
        app.UPLOADS.mkdir(parents=True)
        app.OUTPUTS.mkdir(parents=True)
        app.storage = LocalStorage(app.DATA)
        self.adapter = FakeAdapter()
        app.service_adapters = {key: FakeAdapter(False) for key in app.service_adapters}
        app.service_adapters["outfit_change"] = self.adapter
        app.init_db()
        con = app.db()
        con.execute(
            """INSERT INTO users(email,name,password_hash,credits,role,created_at)
               VALUES('service@example.com','Service User','x',3,'user',?)""",
            (app.now_iso(),)
        )
        self.user_id = con.execute("SELECT id FROM users WHERE email='service@example.com'").fetchone()["id"]
        con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES('service-session',?,?)",
                    (self.user_id, "2999-01-01T00:00:00+00:00"))
        con.commit()
        con.close()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        if self.original_outfit_model is None:
            os.environ.pop("OUTFIT_MODEL", None)
        else:
            os.environ["OUTFIT_MODEL"] = self.original_outfit_model
        self.temp.cleanup()

    def request(self):
        return Request({
            "type": "http", "method": "POST", "path": "/",
            "headers": [(b"cookie", b"mh_session=service-session")]
        })

    @staticmethod
    def image(name="image.png", content=b"image"):
        return UploadFile(filename=name, file=io.BytesIO(content), headers={"content-type": "image/png"})

    def submit_outfit(self, key="same-key", first=None, second=None):
        return asyncio.run(service_routes.create_job(
            "outfit_change", self.request(), prompt="", aspect_ratio="", duration="",
            scale="", restore_face=False, request_key=key, reference_image=None,
            character_image=first or self.image("person.png"),
            outfit_image=second or self.image("outfit.png"),
            source_image=None, background_image=None,
        ))

    def test_create_free_job_and_duplicate_are_idempotent(self):
        first = self.submit_outfit()
        duplicate = self.submit_outfit()
        self.assertFalse(first["duplicate"])
        self.assertTrue(first["free"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(1, self.adapter.submits)
        con = app.db()
        self.assertEqual(1, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        self.assertEqual(3, con.execute("SELECT credits FROM users WHERE id=?", (self.user_id,)).fetchone()["credits"])
        con.close()

    def test_upload_validation_removes_unaccepted_job(self):
        with self.assertRaises(Exception) as raised:
            self.submit_outfit(first=self.image("person.exe"))
        self.assertEqual(400, raised.exception.status_code)
        con = app.db()
        self.assertEqual(0, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        con.close()

    def test_offline_worker_rejects_without_creating_job(self):
        app.service_adapters["outfit_change"] = FakeAdapter(False)
        with self.assertRaises(Exception) as raised:
            self.submit_outfit()
        self.assertEqual(503, raised.exception.status_code)
        self.assertIn("chưa kết nối", raised.exception.detail)
        con = app.db()
        self.assertEqual(0, con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"])
        con.close()

    def test_failure_normalization_and_refund_is_once(self):
        job = self.submit_outfit()
        self.adapter.status_value = {"status": "error", "error": "GPU failed"}
        first = service_routes.refresh_job(self.user_id, job["id"])
        second = service_routes.refresh_job(self.user_id, job["id"])
        self.assertEqual("failed", first["status"])
        self.assertEqual("failed", second["status"])
        con = app.db()
        self.assertEqual(0, con.execute(
            "SELECT COUNT(*) c FROM credit_ledger WHERE ref_type='job_refund'"
        ).fetchone()["c"])
        con.close()

    def test_background_requires_reference_or_prompt(self):
        with self.assertRaises(Exception) as raised:
            service_routes.validate_request(
                "background_change", "", "", "", "", False,
                {"source_image": self.image(), "background_image": None}
            )
        self.assertEqual(400, raised.exception.status_code)


class StatusNormalizationTests(unittest.TestCase):
    def test_worker_statuses_are_normalized(self):
        expected = {
            "pending": "queued", "running": "processing", "in_progress": "processing",
            "succeeded": "completed", "error": "failed", "canceled": "cancelled",
        }
        self.assertEqual(expected, {value: normalize_status(value) for value in expected})

class ServicePageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        static = Path(__file__).resolve().parents[1] / "static"
        cls.service_html = (static / "service.html").read_text(encoding="utf-8")
        cls.service_js = (static / "service.js").read_text(encoding="utf-8")
        cls.toolbar_js = (static / "global-toolbar.js").read_text(encoding="utf-8")
        cls.app_html = (static / "app.html").read_text(encoding="utf-8")
        cls.app_js = (static / "app.js").read_text(encoding="utf-8")
        cls.responsive_css = (static / "responsive.css").read_text(encoding="utf-8")

    def test_service_script_uses_toolbar_balance_id_that_exists(self):
        self.assertIn('id="mobileToolbarCredits"', self.toolbar_js)
        self.assertIn("document.getElementById('mobileToolbarCredits').textContent", self.service_js)
        self.assertNotIn("$('balance')", self.service_js)

    def test_each_service_renders_its_required_form_contract(self):
        expected = {
            "video_generation": ("prompt", "reference_image", "aspect_ratio", "duration"),
            "outfit_change": ("character_image", "outfit_image", "prompt"),
            "background_change": ("source_image", "background_image", "prompt"),
            "image_upscale": ("source_image", "scale", "restore_face"),
        }
        for service_key, fields in expected.items():
            with self.subTest(service=service_key):
                self.assertIn(f"key==='{service_key}'", self.service_js)
                for field in fields:
                    self.assertTrue(
                        f"'{field}'" in self.service_js or f'name="{field}"' in self.service_js,
                        f"{service_key} is missing {field}",
                    )
        self.assertIn('id="dynamicFields"', self.service_html)
        self.assertIn('id="submitButton"', self.service_html)

    def test_offline_warning_does_not_prevent_form_render(self):
        warning = self.service_js.index("if(unavailable)")
        render = self.service_js.index("renderFields()", warning)
        self.assertGreater(render, warning)
        self.assertNotIn("return", self.service_js[warning:render])

    def test_motion_transfer_keeps_its_dedicated_form(self):
        self.assertIn('id="jobForm"', self.app_html)
        self.assertIn('name="image"', self.app_html)
        self.assertIn('name="motion"', self.app_html)
        self.assertIn('value="AI Motion Studio"', self.app_html)

    def test_mobile_toolbar_uses_six_equal_columns_without_overflow(self):
        fluid = self.responsive_css[self.responsive_css.index("/* V3 shared six-tab mobile navigation"):]
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))", fluid)
        self.assertIn("width:100%", fluid)
        self.assertIn("max-width:none", fluid)
        self.assertIn("min-width:0", fluid)
        self.assertNotIn("zoom:", fluid)
        self.assertNotIn("transform:scale", fluid.replace(" ", ""))

    def test_toolbar_has_one_canonical_active_state(self):
        navigation_markup = self.toolbar_js[self.toolbar_js.index('<nav class="global-actions'):self.toolbar_js.index('</nav>')]
        self.assertEqual(6, navigation_markup.count('data-tool="'))
        set_active = self.toolbar_js[self.toolbar_js.index("function setActive"):self.toolbar_js.index("function applyLanguage")]
        self.assertIn("removeAttribute('aria-current')", set_active)
        self.assertIn("setAttribute('aria-current','page')", set_active)
        self.assertNotIn("mobile-active", self.app_js[self.app_js.index("function updateMobileToolState"):self.app_js.index("function goto")])

    def test_account_state_comes_from_backend(self):
        self.assertIn("fetch('/api/me'", self.toolbar_js)
        self.assertIn("applySignedOut()", self.toolbar_js)
        self.assertIn("applySignedIn(await response.json())", self.toolbar_js)
        self.assertIn("fetch('/api/logout'", self.toolbar_js)
        self.assertIn("aria-expanded", self.toolbar_js)
        self.assertIn("aria-controls", self.toolbar_js)

    def test_account_menu_items_are_in_required_order(self):
        required = [
            'data-account-label="history"',
            'data-account-label="topup"',
            'data-account-label="support"',
            'data-account-label="profile"',
            'data-account-label="commission"',
            'data-account-label="logout"',
        ]
        positions = [self.toolbar_js.index(item) for item in required]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn(">Credits<", self.toolbar_js)

    def test_account_menu_open_close_contract(self):
        self.assertIn("menuOpen?closeMenu():openMenu()", self.toolbar_js)
        self.assertIn("if(menuOpen&&!host.contains(event.target))closeMenu()", self.toolbar_js)
        self.assertIn("event.key==='Escape'&&menuOpen", self.toolbar_js)
        self.assertIn("data-tool=\"account\"", self.toolbar_js)
        self.assertIn("menu.querySelectorAll('a')", self.toolbar_js)

    def test_shared_header_fixed_contract_uses_measured_spacer(self):
        final = self.responsive_css[self.responsive_css.index("/* Final shared-header contract:"):]
        self.assertIn("position:fixed!important", final)
        self.assertIn("padding-top:var(--tvc-toolbar-height)", final)
        self.assertIn("repeat(5,minmax(0,1fr))", final)
        self.assertIn("width:min(82vw,340px)", final)
        self.assertIn("prefers-reduced-motion:reduce", final)
        self.assertIn("ResizeObserver", self.toolbar_js)
        self.assertIn("--tvc-toolbar-height", self.toolbar_js)
        self.assertIn("orientationchange", self.toolbar_js)

    def test_active_feedback_is_immediate_and_layout_stable(self):
        self.assertIn("addEventListener('pointerdown'", self.toolbar_js)
        final = self.responsive_css[self.responsive_css.index("/* Final shared-header contract:"):]
        self.assertIn("transition:background-color .22s ease", final)
        self.assertIn("transform:none!important", final)

    def test_blue_fixed_header_and_compact_account_menu_contract(self):
        final = self.responsive_css[self.responsive_css.index("/* Blue liquid-glass toolbar"):]
        self.assertIn("position:fixed!important", final)
        self.assertIn("padding-top:var(--header-height)", final)
        self.assertIn("z-index:9000!important", final)
        self.assertIn("repeat(5,minmax(0,1fr))", final)
        self.assertIn("width:min(78vw,300px)", final)
        self.assertIn("right:max(10px,env(safe-area-inset-right,0px))", final)
        self.assertIn("rgba(16,42,92,.96)", final)
        self.assertIn("blur(18px) saturate(145%)", final)
        self.assertIn("rgba(143,99,255,.92)", final)
        self.assertIn("classList.add('tvc-fixed-toolbar')", self.toolbar_js)
        self.assertIn("--header-height", self.toolbar_js)

    def test_mobile_navigation_buttons_keep_horizontal_rectangle_contract(self):
        final = self.responsive_css[self.responsive_css.index("/* Blue liquid-glass toolbar"):]
        self.assertIn("height:clamp(58px,14vw,66px)", final)
        self.assertIn("border-radius:clamp(14px,4vw,18px)", final)
        self.assertIn("gap:clamp(2px,.8vw,6px)", final)
        self.assertNotIn("aspect-ratio:1/1", final.replace(" ", ""))
        self.assertNotIn("aspect-ratio:1 / 1", final)


class GlobalDrawerRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.toolbar = (root / "static/global-toolbar.js").read_text(encoding="utf-8")
        cls.css = (root / "static/responsive.css").read_text(encoding="utf-8")

    def test_menu_is_first_and_drawer_has_no_duplicate_navigation_group(self):
        nav = self.toolbar[self.toolbar.index('<nav class="global-actions'):self.toolbar.index('</nav>')]
        order = [nav.index(f'data-tool="{name}"') for name in ("menu", "models", "history", "affiliate", "wallet", "account")]
        self.assertEqual(order, sorted(order))
        drawer = self.toolbar[self.toolbar.index('id="aiToolsDrawer"'):self.toolbar.index('</aside>')]
        self.assertNotIn("<summary>Điều hướng</summary>", drawer)
        self.assertEqual(1, self.toolbar.count('id="aiToolsDrawer"'))
        self.assertEqual(1, self.toolbar.count('id="aiToolsOverlay"'))

    def test_rendered_navigation_dom_has_canonical_direct_child_order(self):
        class NavigationDOMParser(HTMLParser):
            def __init__(self):
                super().__init__();self.in_nav=False;self.depth=0;self.tools=[]
            def handle_starttag(self, tag, attrs):
                attributes=dict(attrs)
                if tag=="nav" and "global-actions" in attributes.get("class","").split():
                    self.in_nav=True;self.depth=1;return
                if self.in_nav:
                    if self.depth==1 and attributes.get("data-tool"):
                        self.tools.append(attributes["data-tool"])
                    self.depth+=1
            def handle_endtag(self, tag):
                if self.in_nav:
                    self.depth-=1
                    if self.depth==0:self.in_nav=False

        template_start=self.toolbar.index("host.innerHTML=`")+len("host.innerHTML=`")
        template_end=self.toolbar.index("`;",template_start)
        parser=NavigationDOMParser()
        parser.feed(self.toolbar[template_start:template_end])
        self.assertEqual(["menu","models","history","affiliate","wallet","account"],parser.tools)
        self.assertEqual("menu",parser.tools[0])
        self.assertIn("navRow.firstElementChild!==menuTab",self.toolbar)
        self.assertIn("navRow.prepend(menuTab)",self.toolbar)
        self.assertGreaterEqual(self.toolbar.count("ensureMenuTabFirst()"),4)
        self.assertIn("new MutationObserver(ensureMenuTabFirst)",self.toolbar)
        self.assertIn("navOrderObserver.observe(navRow,{childList:true})",self.toolbar)
        self.assertIn("navOrderObserver.disconnect()",self.toolbar)
        self.assertNotIn("appendChild(tab)",self.toolbar)
        self.assertNotRegex(self.css,r"\.(menu|home|history|about|vip|account|login)-tab\s*\{[^}]*order:")
        self.assertNotIn(":nth-child",self.css[self.css.index("/* Drawer gesture"):])

    def test_backdrop_consumes_the_whole_input_sequence(self):
        for event in ("pointerdown", "pointerup", "touchstart", "touchend", "click"):
            self.assertIn(f"'{event}'", self.toolbar)
        self.assertIn("event.preventDefault()", self.toolbar)
        self.assertIn("event.stopPropagation()", self.toolbar)
        self.assertIn("event.stopImmediatePropagation()", self.toolbar)
        self.assertIn("touch-action:none", self.css)
        self.assertIn("document.body.append(toolsOverlay,toolsDrawer)", self.toolbar)
        self.assertIn("capture:true", self.toolbar)
        self.assertIn("transitionend", self.toolbar)
        self.assertIn("backdropSequenceActive", self.toolbar)
        self.assertIn("height:100dvh", self.css)
        self.assertIn("z-index:100000", self.css)

    def test_all_explicit_close_controls_remain_connected(self):
        self.assertIn("toggleTools", self.toolbar)
        self.assertIn("aiToolsClose'),'click',closeTools", self.toolbar)
        self.assertIn("event.key==='Escape'&&toolsDrawer.classList.contains('open')", self.toolbar)
        self.assertIn("querySelectorAll('a').forEach(link=>listen(link,'click',closeTools))", self.toolbar)

    def test_swipe_boundaries_thresholds_and_vertical_cancel(self):
        self.assertIn("p.x<24||p.x>80", self.toolbar)
        self.assertIn("dx>=60", self.toolbar)
        self.assertIn("dx<=-60", self.toolbar)
        self.assertIn("Math.abs(dy)>30", self.toolbar)
        self.assertIn("Math.abs(dx)<=Math.abs(dy)*1.35", self.toolbar)
        self.assertIn("touchstart',startOpenGesture", self.toolbar)
        self.assertIn("pointerdown',startOpenGesture", self.toolbar)

    def test_gesture_exclusions_and_listener_cleanup(self):
        for selector in ("input", "textarea", "select", "button", "video", "data-no-drawer-gesture", "upload-tile"):
            self.assertIn(selector, self.toolbar)
        self.assertIn("overflowX", self.toolbar)
        self.assertIn("window.__tvcToolbarAbort?.abort()", self.toolbar)
        self.assertIn("signal=toolbarAbort.signal", self.toolbar)
        self.assertIn("toolbarResizeObserver?.disconnect()", self.toolbar)


if __name__ == "__main__":
    unittest.main()
class ReferenceVideoValidationTests(unittest.TestCase):
    @staticmethod
    def completed(codec="h264", fps="30000/1001", duration="5.0", returncode=0):
        payload = {"streams": [{"codec_type": "video", "codec_name": codec,
                                "avg_frame_rate": fps, "duration": duration}],
                   "format": {"duration": duration}}
        return type("Completed", (), {"returncode": returncode,
                    "stdout": __import__("json").dumps(payload)})()

    def test_accepts_h264_and_h265_in_supported_range(self):
        from unittest.mock import patch
        for codec in ("h264", "hevc"):
            with self.subTest(codec=codec), patch("service_routes.shutil.which", return_value="/usr/bin/ffprobe"), patch("service_routes.subprocess.run", return_value=self.completed(codec=codec)):
                result = service_routes.probe_reference_video(Path("sample.mp4"))
                self.assertEqual(codec, result["codec"])

    def test_rejects_codec_fps_duration_and_total_duration(self):
        from unittest.mock import patch
        cases = [("vp9", "30/1", "5"), ("h264", "20/1", "5"), ("h264", "30/1", "1")]
        for codec, fps, duration in cases:
            with self.subTest(codec=codec, fps=fps, duration=duration), patch("service_routes.shutil.which", return_value="ffprobe"), patch("service_routes.subprocess.run", return_value=self.completed(codec, fps, duration)):
                with self.assertRaises(Exception) as raised:
                    service_routes.probe_reference_video(Path("sample.mov"))
                self.assertEqual(400, raised.exception.status_code)
        with patch("service_routes.probe_reference_video", side_effect=[{"duration": 8, "fps": 30, "codec": "h264"}, {"duration": 8, "fps": 30, "codec": "hevc"}]):
            with self.assertRaises(Exception) as raised:
                service_routes.validate_reference_video_set([Path("a.mp4"), Path("b.mov")])
            self.assertEqual(400, raised.exception.status_code)

    def test_missing_ffprobe_is_configuration_error(self):
        from unittest.mock import patch
        with patch("service_routes.shutil.which", return_value=None):
            with self.assertRaises(Exception) as raised:
                service_routes.probe_reference_video(Path("sample.mp4"))
            self.assertEqual(503, raised.exception.status_code)
