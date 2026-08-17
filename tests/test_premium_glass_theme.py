from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
ZALO_URL = "https://zalo.me/g/zjsk2eclgz9dejbfsmgz"


class PremiumGlassThemeTests(unittest.TestCase):
    def test_zalo_link_is_available_in_dashboard_and_shared_drawer(self):
        app_html = (STATIC / "app.html").read_text(encoding="utf-8")
        toolbar_js = (STATIC / "global-toolbar.js").read_text(encoding="utf-8")

        for source in (app_html, toolbar_js):
            self.assertIn(ZALO_URL, source)
            self.assertIn('target="_blank"', source)
            self.assertIn('rel="noopener noreferrer"', source)
            self.assertIn('aria-label="Tham gia nhóm Zalo', source)


    def test_premium_glass_theme_exposes_shared_tokens_and_accessibility_guards(self):
        css = (STATIC / "theme-purple.css").read_text(encoding="utf-8")

        for token in (
            "--bg-primary",
            "--bg-secondary",
            "--glass-surface",
            "--glass-surface-strong",
            "--glass-border",
            "--glass-highlight",
            "--text-primary",
            "--text-secondary",
            "--accent-purple",
            "--accent-blue",
            "--accent-cyan",
            "--accent-pink",
            "--shadow-glass",
            "--shadow-glow",
            "--radius-card",
            "--transition-ui",
        ):
            self.assertIn(token, css)

        self.assertIn("@media (hover:hover) and (pointer:fine)", css)
        self.assertIn("@media (prefers-reduced-motion:reduce)", css)
        self.assertIn("@supports not ((backdrop-filter:blur(1px))", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("min-height:44px", css)
