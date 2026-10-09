"""Prevent Save/Cancel actions from disappearing below long CRM record forms."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_long_record_modal_has_scrolling_body_and_fixed_action_footer():
    html = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/spacing.css").read_text(encoding="utf-8")
    assert 'id="record-form"' in html
    assert 'id="modal-submit"' in html
    assert 'id="modal-cancel"' in html
    assert '#modal-backdrop #record-form { display:flex;' in css
    assert 'flex-direction:column; min-height:0; overflow:hidden;' in css
    assert '#modal-backdrop #modal-body { flex:1 1 auto; min-height:0; overflow-y:auto;' in css
    assert '#modal-backdrop #record-form > .modal-foot { display:flex; flex:0 0 auto;' in css
    assert 'max-height:calc(100dvh - 32px)' in css
    assert 'max-height:calc(100dvh - 16px)' in css
