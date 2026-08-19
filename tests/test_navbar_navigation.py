import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class NavbarNavigationAndOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toolbar_js = (STATIC / "global-toolbar.js").read_text(encoding="utf-8")
        cls.styles_css = (STATIC / "styles.css").read_text(encoding="utf-8")
        cls.purple_css = (STATIC / "theme-purple.css").read_text(encoding="utf-8")
        cls.responsive_css = (STATIC / "responsive.css").read_text(encoding="utf-8")
        cls.app_js = (STATIC / "app.js").read_text(encoding="utf-8")

    def test_toolbar_has_high_z_index_and_pointer_events(self):
        # Ensure toolbar has high z-index and active pointer-events
        self.assertIn("z-index:9000!important;pointer-events:auto!important", self.purple_css)
        self.assertIn(".global-toolbar *,.global-actions *,.liquid-nav *", self.purple_css)

    def test_overlays_are_strictly_pointer_events_none_when_hidden(self):
        # Ensure ai-tools-overlay, modal-wrap, gallery-modal have pointer-events: none when not open
        self.assertIn(".ai-tools-overlay:not(.open),.ai-tools-overlay[hidden]", self.purple_css)
        self.assertIn("display:none!important;pointer-events:none!important;visibility:hidden!important", self.purple_css)
        self.assertIn(".ai-tools-overlay[hidden],.ai-tools-overlay:not(.open):not(:not([hidden])){display:none!important;pointer-events:none!important;visibility:hidden!important}", self.responsive_css)

    def test_tools_overlay_state_management_in_js(self):
        # In global-toolbar.js, overlay is hidden and pointer-events disabled at init and close
        self.assertIn("toolsOverlay.hidden=true;toolsOverlay.style.display='none';toolsOverlay.style.pointerEvents='none'", self.toolbar_js)

    def test_navbar_routing_elements_and_click_handlers(self):
        # Trang Chu -> href="/"
        self.assertIn('href="/" class="tool-pill liquid-pill home-tab" data-tool="models"', self.toolbar_js)
        # Lich Su -> href="/app#jobs"
        self.assertIn('href="/app#jobs" class="tool-pill liquid-pill history-tab" data-tool="history"', self.toolbar_js)
        # Gioi Thieu -> href="/about"
        self.assertIn('href="/about" class="tool-pill liquid-pill about-tab" data-tool="affiliate"', self.toolbar_js)
        # Nap VIP -> href="/pricing"
        self.assertIn('href="/pricing" class="tool-pill liquid-pill vip-tab" data-tool="wallet"', self.toolbar_js)
        # Dang Nhap -> trigger with tvcOpenLoginModal call
        self.assertIn("window.tvcOpenLoginModal(location.pathname + location.search + location.hash)", self.toolbar_js)

    def test_toolbar_swipe_gestures_are_excluded_on_navbar(self):
        # Ensure toolbar buttons are in blockedGestureTarget so swipe gestures never intercept taps
        self.assertIn(".global-toolbar,.liquid-toolbar,.global-actions,.tool-pill", self.toolbar_js)


if __name__ == "__main__":
    unittest.main()
