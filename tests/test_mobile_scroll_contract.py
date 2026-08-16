from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_app_uses_document_scroll_and_dynamic_viewport_height():
    css = (ROOT / "static" / "responsive.css").read_text(encoding="utf-8")

    assert "body.app-body{" in css
    assert "height:auto!important;" in css
    assert "min-height:100dvh!important;" in css
    assert "overflow-y:auto!important;" in css
    assert ".app-body .workspace{overflow:visible!important}" in css
    assert "min-height:calc(100dvh - 86px)!important;" in css


def test_mobile_create_action_reserves_iphone_safe_area():
    css = (ROOT / "static" / "responsive.css").read_text(encoding="utf-8")
    html = (ROOT / "static" / "app.html").read_text(encoding="utf-8")

    assert "margin-bottom:calc(24px + env(safe-area-inset-bottom,0px))!important;" in css
    assert 'class="simple-render-btn quick single-render-btn" type="submit"' in html
    assert "Tạo Video" in html


def test_mobile_drawer_body_lock_is_scoped_and_restored():
    css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "global-toolbar.js").read_text(encoding="utf-8")

    assert "body.ai-tools-open{overflow:hidden}" in css
    assert "document.body.classList.add('ai-tools-open')" in js
    assert "document.body.classList.remove('ai-tools-open')" in js
