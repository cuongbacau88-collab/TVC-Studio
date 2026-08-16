from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class ServiceCardNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.service_html = (STATIC / "service.html").read_text(encoding="utf-8")
        cls.metadata = (STATIC / "service-metadata.js").read_text(encoding="utf-8")
        cls.navigation = (STATIC / "service-card-navigation.js").read_text(encoding="utf-8")
        cls.service_js = (STATIC / "service.js").read_text(encoding="utf-8")
        cls.responsive = (STATIC / "responsive.css").read_text(encoding="utf-8")

    def test_exact_card_route_mapping(self):
        mappings = {
            "AI Motion Studio": "/app?tool=motion",
            "AI Video Creator": "/services/video_generation",
            "AI Đổi Trang Phục": "/services/outfit_change",
            "AI Đổi Bối Cảnh": "/services/background_change",
            "AI Nâng Cấp Ảnh": "/services/image_upscale",
        }
        for title, route in mappings.items():
            self.assertIn(f'data-service-href="{route}"', self.home, title)
            self.assertIn(f'href="{route}"', self.home, title)

    def test_all_cards_support_pointer_and_keyboard_navigation(self):
        self.assertEqual(5, self.home.count('service-navigation-card'))
        self.assertEqual(5, self.home.count('role="link" tabindex="0"'))
        self.assertIn("location.assign(href)", self.navigation)
        self.assertIn("event.key!=='Enter'&&event.key!==' '", self.navigation)
        self.assertIn("event.target.closest(interactive)", self.navigation)

    def test_decorative_layers_do_not_intercept_card_taps(self):
        self.assertIn(".service-navigation-card::before", self.responsive)
        self.assertIn(".service-navigation-card::after{pointer-events:none!important}", self.responsive)

    def test_service_metadata_is_rendered_before_catalog_fetch(self):
        self.assertIn("service-metadata.js?v=20260816.1", self.service_html)
        self.assertLess(self.service_html.index("service-metadata.js"), self.service_html.index("service.js?v=20260816.1"))
        self.assertIn("window.TVCServiceDefinitions=definitions", self.metadata)
        self.assertIn("const definitions=window.TVCServiceDefinitions||{}", self.service_js)
        self.assertLess(self.service_js.index("$('serviceTitle').textContent=def.title"), self.service_js.index("await api('/api/services')"))

    def test_image_tools_never_use_video_descriptions(self):
        expected = {
            "outfit_change": ("trang phục tham chiếu", "tạo ảnh mới"),
            "background_change": ("ảnh bối cảnh", "tạo ảnh"),
            "image_upscale": ("ảnh chất lượng cao",),
        }
        for key, phrases in expected.items():
            block = re.search(rf"{key}:Object\.freeze\(\{{(.*?)\}}\)", self.metadata, re.S)
            self.assertIsNotNone(block, key)
            for phrase in phrases:
                self.assertIn(phrase, block.group(1))

    def test_image_tools_hide_video_only_gallery_and_copy(self):
        self.assertIn('id="serviceReferenceGallery"', self.service_html)
        self.assertIn("gallery.hidden=definition.output!=='video'", self.metadata)
        self.assertIn("Đăng nhập để xử lý ảnh", self.metadata)
        self.assertEqual(3, self.metadata.count("output:'image'"))
        self.assertEqual(1, self.metadata.count("output:'video'"))

    def test_service_routes_have_static_backend_fallback(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/services/{service_key}")', app_source)
        self.assertIn('return FileResponse(BASE / "static" / "service.html")', app_source)


if __name__ == "__main__":
    unittest.main()
