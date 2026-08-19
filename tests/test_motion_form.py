from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/"static"


class MotionFormRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(STATIC/"app.html").read_text(encoding="utf-8")
        cls.app=(STATIC/"app.js").read_text(encoding="utf-8")
        cls.form=(STATIC/"motion-form.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"motion-form.css").read_text(encoding="utf-8")

    def test_frontend_limits_match_existing_backend_contract(self):
        self.assertIn("MAX_IMAGE_BYTES=25*1024*1024",self.form)
        self.assertIn("MAX_VIDEO_BYTES=300*1024*1024",self.form)
        for ext in ("png","jpg","jpeg","webp"):
            self.assertIn(f"'{ext}'",self.form)
        for ext in ("mp4","mov","webm"):
            self.assertIn(f"'{ext}'",self.form)

    def test_image_and_video_preview_have_object_url_cleanup(self):
        self.assertIn("URL.createObjectURL(file)",self.form)
        self.assertIn("URL.revokeObjectURL(imageUrl)",self.form)
        self.assertIn("URL.revokeObjectURL(motionUrl)",self.form)
        self.assertIn("window.addEventListener('pagehide'",self.form)
        self.assertIn("window.addEventListener('pageshow'",self.form)
        self.assertIn("if(!event.persisted)return",self.form)
        self.assertIn('id="imagePreview"',self.html)
        self.assertIn('id="motionPreview"',self.html)

    def test_duration_is_enforced_before_submit(self):
        self.assertIn("MIN_DURATION=10",self.form)
        self.assertIn("MAX_DURATION=20",self.form)
        self.assertIn("duration<MIN_DURATION||duration>MAX_DURATION",self.form)
        self.assertIn("await motionForm.validateForSubmit()",self.app)

    def test_aspect_ratio_remains_single_source_of_truth(self):
        self.assertIn('id="aspectRatio" value="9:16"',self.html)
        self.assertEqual(1,self.html.count('class="simple-aspect active"'))
        self.assertIn("$('#aspectRatio').value=btn.dataset.aspect",self.app)
        self.assertIn("['9:16','16:9'].includes(aspectInput.value)",self.form)

    def test_create_button_starts_disabled_and_unlocks_only_when_valid(self):
        self.assertIn('type="submit" disabled aria-disabled="true"',self.html)
        self.assertIn("const disabled=locked||!motionForm?.isValid()",self.app)
        self.assertIn("imageValid&&motionValid",self.form)

    def test_double_submit_guard_is_preserved(self):
        self.assertIn("if(jobSubmitLocked) return",self.app)
        self.assertIn("setJobSubmitLocked(true,submitter)",self.app)
        self.assertIn("setJobSubmitLocked(false)",self.app)

    def test_submit_stays_on_create_page_with_queue_actions(self):
        self.assertIn("showMotionQueuedState(j)",self.app)
        self.assertNotIn("goto('jobs');",self.app)
        self.assertIn("motionQueuedHistory",self.html)
        self.assertIn("motionContinueButton",self.html)
        self.assertIn("motionSubmitError",self.html)
        self.assertIn("showMotionSubmitError(err)",self.app)
        self.assertIn("Đang gửi tác vụ...",self.app)
        self.assertIn("reset:()=>",self.form)

    def test_mobile_preview_is_bounded_without_touching_scroll_contract(self):
        self.assertIn("max-width:100%",self.css)
        self.assertIn("max-height:240px",self.css)
        responsive=(STATIC/"responsive.css").read_text(encoding="utf-8")
        self.assertIn("body.app-body{",responsive)
        self.assertIn("overflow-y:auto!important",responsive)


if __name__=="__main__":
    unittest.main()
