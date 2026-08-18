from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VideoCreatorFirstLastFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.creator = (ROOT / "static" / "video-creator.js").read_text(encoding="utf-8")
        cls.service = (ROOT / "static" / "service.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "service.css").read_text(encoding="utf-8")

    def test_independent_start_and_end_fields_are_real_file_inputs(self):
        self.assertIn("endpointCard('first','Ảnh bắt đầu','first_frame')", self.creator)
        self.assertIn("endpointCard('last','Ảnh kết thúc','last_frame')", self.creator)
        self.assertIn('name="${field}" data-endpoint="${slot}"', self.creator)
        self.assertNotIn('aria-label="${label}" required', self.creator)
        self.assertNotIn(".upload-tile input,.add-reference input{position:absolute;opacity:0;pointer-events:none}", self.css)
        self.assertIn("inset:0;width:100%;height:100%", self.css)

    def test_preview_replace_remove_and_object_url_cleanup(self):
        self.assertIn("endpoint-preview", self.creator)
        self.assertIn("objectUrl(file)", self.creator)
        self.assertIn("revokeFile(state[slot])", self.creator)
        self.assertIn("data-remove-endpoint", self.creator)
        self.assertIn("revokeAll()", self.creator)
        self.assertIn("URL.revokeObjectURL", self.creator)

    def test_first_last_validation_has_specific_messages(self):
        self.assertIn("Cần đủ ảnh bắt đầu và ảnh kết thúc.", self.creator)
        self.assertIn("Cần chọn ảnh bắt đầu.", self.creator)
        self.assertIn("Cần chọn ảnh kết thúc.", self.creator)
        self.assertIn("!state.first||!state.last||!prompt||!ratio||!duration", self.creator)

    def test_first_last_state_matrix_and_stale_error_sync(self):
        self.assertIn("if(state.first&&state.last)return''", self.creator)
        self.assertIn("if(!state.first&&!state.last)return FIRST_LAST_ERRORS[0]", self.creator)
        self.assertIn("return state.first?FIRST_LAST_ERRORS[2]:FIRST_LAST_ERRORS[1]", self.creator)
        self.assertIn("if(!message){if(isEndpointError){error.textContent='';error.classList.add('hidden')}}", self.creator)
        self.assertIn("render();syncSubmit(true)", self.creator)
        self.assertIn("state[slot]=null;render();syncSubmit(true)", self.creator)
        self.assertIn("state.mode==='first_last'&&firstLastError()", self.creator)

    def test_replace_and_remove_keep_validation_bound_to_file_state(self):
        self.assertIn("revokeFile(state[slot]);state[slot]=file", self.creator)
        self.assertIn("revokeFile(state[slot]);state[slot]=null", self.creator)
        self.assertNotIn("querySelector('[name=first_frame]').files", self.creator)
        self.assertNotIn("querySelector('[name=last_frame]').files", self.creator)

    def test_formdata_uses_backend_keys_and_preserves_double_submit_guard(self):
        self.assertIn("data.set('first_frame',event.currentTarget.__creatorFiles.first)", self.service)
        self.assertIn("data.set('last_frame',event.currentTarget.__creatorFiles.last)", self.service)
        self.assertIn("if(submitting)return", self.service)
        self.assertIn("first:state.first,last:state.last", self.creator)

    def test_mobile_preview_is_bounded_without_scroll_override(self):
        self.assertIn(".first-last-grid{grid-template-columns:1fr}", self.css)
        self.assertIn("width:100%;height:220px;object-fit:contain", self.css)
        self.assertNotIn("overflow-y:hidden", self.css)


class FFprobeDeploymentContractTests(unittest.TestCase):
    def test_nixpacks_installs_ffmpeg_without_replacing_provider_packages(self):
        config = (ROOT / "nixpacks.toml").read_text(encoding="utf-8")
        self.assertIn("[phases.setup]", config)
        self.assertIn('aptPkgs = ["ffmpeg"]', config)
        self.assertNotIn('"..."', config)
        self.assertNotIn("providers", config)
        self.assertNotIn("[start]", config)


if __name__ == "__main__":
    unittest.main()
