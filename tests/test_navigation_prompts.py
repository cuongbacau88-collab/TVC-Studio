from pathlib import Path
import unittest


STATIC = Path(__file__).resolve().parents[1] / "static"


class VideoPromptRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.creator = (STATIC / "video-creator.js").read_text(encoding="utf-8")

    def test_reference_modes_have_exact_default_prompt(self):
        prompt = "Tạo video chuyển động tự nhiên từ hình ảnh và video tham chiếu, giữ ổn định khuôn mặt, nhân vật và trang phục."
        self.assertEqual(2, self.creator.count(prompt))
        self.assertIn("reference_images:'" + prompt, self.creator)
        self.assertIn("motion_reference:'" + prompt, self.creator)

    def test_first_last_has_exact_default_prompt(self):
        prompt = "Tạo chuyển động chuyển tiếp tự nhiên từ ảnh bắt đầu đến ảnh kết thúc, giữ nhân vật ổn định và chuyển động mượt mà."
        self.assertIn("first_last:'" + prompt, self.creator)

    def test_user_prompt_is_not_overwritten_when_switching_mode(self):
        self.assertIn("const keepPrompt=state.promptDirty", self.creator)
        self.assertIn("if(!keepPrompt)state.prompt=DEFAULT_PROMPTS[state.mode]", self.creator)

    def test_blank_prompt_is_restored_before_formdata_submission(self):
        self.assertIn("if(!state.prompt.trim())", self.creator)
        self.assertIn("prompt.value=state.prompt", self.creator)
        self.assertIn("DEFAULT_PROMPTS[state.mode]", self.creator)

    def test_files_are_not_persisted_and_refresh_warning_exists(self):
        self.assertNotIn("JSON.stringify(state.images)", self.creator)
        self.assertNotIn("JSON.stringify(state.videos)", self.creator)
        self.assertIn("Vui lòng chọn lại file", self.creator)


class ReturnToRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toolbar = (STATIC / "global-toolbar.js").read_text(encoding="utf-8")
        cls.app = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.google = (STATIC / "google-login.js").read_text(encoding="utf-8")
        cls.service = (STATIC / "service.js").read_text(encoding="utf-8")

    def test_service_login_uses_return_to(self):
        self.assertIn("link.href=window.TVCReturnNavigation.loginUrl()", self.service)
        self.assertIn("location.href=loginUrl()", self.toolbar)

    def test_path_query_and_hash_are_preserved(self):
        self.assertIn("location.pathname+location.search+location.hash", self.toolbar)
        self.assertIn("return url.pathname+url.search+url.hash", self.toolbar)

    def test_no_return_to_falls_back_home(self):
        self.assertIn("return '/'", self.toolbar)
        self.assertIn("consumeReturn()||'/'", self.app)

    def test_absolute_and_protocol_relative_urls_are_rejected(self):
        self.assertIn("!value.startsWith('/')", self.toolbar)
        self.assertIn("value.startsWith('//')", self.toolbar)
        self.assertIn("url.origin!==location.origin", self.toolbar)

    def test_dashboard_sections_are_valid_return_targets(self):
        for value in ("#jobs", "#affiliate", "#wallet"):
            self.assertIn(value, self.toolbar)

    def test_google_login_supports_current_global_toolbar(self):
        self.assertIn("#toolbarAccountTrigger", self.google)
        self.assertIn("#toolbarAccountLabel", self.google)
        self.assertIn("#toolbarAccountIcon", self.google)

    def test_email_and_google_login_consume_same_return_target(self):
        self.assertIn("TVCReturnNavigation?.consumeReturn()", self.app)
        self.assertIn("TVCReturnNavigation?.consumeReturn()", self.google)
        self.assertIn("return_to=${encodeURIComponent(returnTo)}", self.google)


if __name__ == "__main__":
    unittest.main()
