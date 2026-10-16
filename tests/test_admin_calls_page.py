"""석원 TODO 1-3 직원 호출 관리자 화면 테스트."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]
APP = str(ROOT / "admin" / "app.py")


def _open_calls(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_SKIP_TOKEN", "0")
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["page"] = "직원 호출"
    app.run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_calls_page_shows_pending_before_completed(monkeypatch):
    app = _open_calls(monkeypatch)
    assert not app.exception
    assert app.sidebar.radio(key="nav_top").value == "직원 호출"
    assert any(markdown.value == "#### 7번 테이블" for markdown in app.markdown)
    assert len([button for button in app.button if button.key and button.key.startswith("call_done_")]) == 3


def test_call_can_be_marked_done(monkeypatch):
    app = _open_calls(monkeypatch)
    before = [button for button in app.button if button.key and button.key.startswith("call_done_")]
    before[0].click().run()
    after = [button for button in app.button if button.key and button.key.startswith("call_done_")]
    assert not app.exception
    assert len(after) == len(before) - 1
