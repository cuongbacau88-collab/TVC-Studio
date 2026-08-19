import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class GuestAccessFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home_html = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.app_html = (STATIC / "app.html").read_text(encoding="utf-8")
        cls.app_js = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.service_html = (STATIC / "service.html").read_text(encoding="utf-8")
        cls.service_js = (STATIC / "service.js").read_text(encoding="utf-8")

    def test_homepage_cta_buttons_do_not_intercept_auth(self):
        # Ensure no click-interceptor on model buttons that forces openLoginModal on click
        self.assertNotIn("document.querySelectorAll('.model-button, #motionPlayerCreateBtn').forEach", self.home_html)
        
        # Verify routing links for all 5 services exist
        self.assertIn('href="/app?tool=motion"', self.home_html)
        self.assertIn('href="/services/video_generation"', self.home_html)
        self.assertIn('href="/services/outfit_change"', self.home_html)
        self.assertIn('href="/services/background_change"', self.home_html)
        self.assertIn('href="/services/image_upscale"', self.home_html)

    def test_app_workspace_unblocks_guest_and_uses_modal(self):
        # app.html has modal-wrap for authGate with a close button
        self.assertIn('id="authGate" class="modal-wrap"', self.app_html)
        self.assertIn('id="loginClose"', self.app_html)

        # app.js boot allows guest to see dashboard without hiding it
        self.assertIn("me=null;showDashboard()", self.app_js)
        self.assertIn("$('#dashboard')?.classList.remove('hidden')", self.app_js)

        # app.js final action button checks auth before submit
        self.assertIn("if(!me && !window.TVCSignedIn)", self.app_js)
        self.assertIn("showAuth(location.pathname + location.search + location.hash)", self.app_js)

    def test_service_workspaces_allow_guest_and_gate_on_final_action(self):
        # service.html includes login modal, close button, and google-login scripts
        self.assertIn('id="loginModal"', self.service_html)
        self.assertIn('id="loginClose"', self.service_html)
        self.assertIn('/static/google-login.js', self.service_html)

        # service.js does not hide or disable submitButton during init
        self.assertNotIn("$('submitButton').classList.add('hidden')", self.service_js)

        # service.js checks auth on final action submit event
        self.assertIn("if(!window.TVCSignedIn)", self.service_js)
        self.assertIn("openLoginModal(location.pathname+location.search+location.hash)", self.service_js)


if __name__ == "__main__":
    unittest.main()
