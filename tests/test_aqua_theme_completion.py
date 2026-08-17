from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class AquaThemeCompletionTests(unittest.TestCase):
    def test_about_team_copy_is_present_verbatim_and_ordered(self):
        html = (STATIC / "about.html").read_text(encoding="utf-8")
        expected = (
            "✨ TVC STUDIO AI",
            "Dự án được thực hiện bởi",
            "Thảo Điệu Đà",
            "Phương Vy",
            "Quỳnh Chi",
            "⚙️ Vận hành: Nhi An",
            "Sáng tạo bằng AI • Kiếm tiền từ Affiliate • Chia sẻ sức mạnh GPU",
        )
        positions = [html.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('class="legal-card about-team-card"', html)

    def test_drawer_uses_measured_header_height_and_safe_area(self):
        css = (STATIC / "theme-purple.css").read_text(encoding="utf-8")
        self.assertIn("--drawer-top-offset:max(var(--header-height,0px),env(safe-area-inset-top,0px))", css)
        self.assertIn("height:calc(100dvh - var(--drawer-top-offset))", css)
        self.assertIn(".drawer-account b,.drawer-account small", css)

    def test_typography_and_card_surface_contract(self):
        css = (STATIC / "theme-purple.css").read_text(encoding="utf-8")
        self.assertEqual(css.count("fonts.googleapis.com/css2?family=Be+Vietnam+Pro"), 1)
        self.assertIn('--font-ui:"Be Vietnam Pro",Inter', css)
        self.assertIn("--text-heading-light:#073e50", css)
        self.assertIn("--text-primary-dark:#e8f9fc", css)
        self.assertIn("--card-teal-surface:linear-gradient(145deg,rgba(18,101,128,.74),rgba(15,133,151,.62))", css)
        self.assertIn("@media (hover:none),(pointer:coarse)", css)
        self.assertIn("background:var(--card-teal-surface)!important", css)

    def test_all_pages_load_current_theme_version(self):
        pages = list(STATIC.glob("*.html"))
        self.assertTrue(pages)
        for page in pages:
            with self.subTest(page=page.name):
                self.assertIn(
                    "theme-purple.css?v=20260818.3",
                    page.read_text(encoding="utf-8"),
                )
