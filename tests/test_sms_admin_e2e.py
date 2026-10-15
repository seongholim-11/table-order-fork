"""관리자 페이지(Streamlit AppTest) ↔ 실제 백엔드(FastAPI TestClient) 문자 발송 통합 테스트."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.core.settings import Settings
from app.factory import create_app
from app.services.grades import KST
from shared import api

APP = str(ROOT / "admin" / "app.py")
PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]



def go_page(app, page):
    """사이드바에서 메뉴를 연다 (주문 이력·마케팅은 하위 메뉴의 첫 항목)."""
    if page in {"주문 이력": 0, "마케팅": 0}:
        sub = {"주문 이력": "전체 주문", "마케팅": "AI 문자"}[page]
        return app.sidebar.radio(key=f"nav_sub_{page}").set_value(sub).run()
    return app.sidebar.radio(key="nav_top").set_value(page).run()

def make_server(hour=14, **kw):
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None, **kw)
    return create_app(s, sms_clock=lambda: datetime(2026, 10, 12, hour, 0, tzinfo=KST))


def set_profile(c, h, **cols):
    """카카오에서 받아 오는 값과 수신 동의를 테스트용으로 직접 채운다."""
    members = c.app.state.members
    mid = c.get("/api/members/me", headers=h).json()["id"]
    consent = cols.pop("marketing_consent", None)
    for col, val in cols.items():
        members.db.run(f"UPDATE members SET {col}=? WHERE id=?", (val, mid))
    if consent is not None:
        members.set_marketing_consent(mid, consent)


def add_member(c, nick, phone="010-1234-5678", consent=True):
    q = c.post("/api/auth/qr", json={"table_no": 1}).json()
    c.get(f"/api/auth/kakao/start?token={q['token']}")
    c.get("/api/auth/kakao/continue", params={"token": q["token"], "agree": "1" if consent else ""}, follow_redirects=False)
    c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": f"mock-{nick}"})
    h = {"Authorization": f"Bearer {c.get(f'/api/auth/qr/{q['secret']}').json()['access_token']}"}
    set_profile(c, h, phone=phone)
    return h


@pytest.fixture
def server():
    with TestClient(make_server()) as c:
        api.set_client(c)
        yield c
    api.set_client(None)


def login(token="admin-secret"):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value(token)
    app.button[0].click().run()
    return app


def open_marketing(app):
    app.sidebar.radio(key="nav_sub_마케팅").set_value("AI 문자").run()
    assert not app.exception
    return app


def button(app, label):
    return next(b for b in app.get("button") if b.proto.label == label)


def test_login_needs_valid_server_token(server):
    assert login("wrong").error and not login("wrong").session_state["owner"]
    assert login().session_state["owner"] is True


def test_all_admin_pages_render_after_login(server):
    app = login()
    for page in PAGES:
        go_page(app, page)
        assert not app.exception, page


def test_api_mode_without_server_shows_message(monkeypatch):
    import httpx
    monkeypatch.setenv("DATA_SOURCE", "api")
    api.set_client(httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    try:
        app = login()
        assert any("서버에 연결할 수 없습니다" in e.value for e in app.error)
    finally:
        api.set_client(None)


def test_send_dry_run_updates_usage_and_log(server):
    add_member(server, "가"); add_member(server, "나"); add_member(server, "미동의", consent=False)
    app = open_marketing(login())
    app.multiselect[0].set_value(["신규"]).run()
    assert any("발송 대상 2명" in c.value for c in app.caption) and any("DRY RUN" in c.value for c in app.caption)
    send = button(app, "발송")
    assert not send.disabled
    send.click().run()
    usage = server.get("/admin/api/marketing/sms/usage", headers={"Authorization": "Bearer admin-secret"}).json()
    assert sum(usage["used"].values()) == 2
    logs = server.get("/admin/api/marketing/sms/logs", headers={"Authorization": "Bearer admin-secret"}).json()
    assert logs[0]["status"] == "dry_run" and logs[0]["target_count"] == 2
    assert not app.exception


def test_send_blocked_at_night_and_without_targets():
    with TestClient(make_server(hour=22)) as c:
        api.set_client(c)
        try:
            add_member(c, "가")
            app = open_marketing(login())
            app.multiselect[0].set_value(["신규"]).run()
            assert any("야간" in w.value for w in app.warning) and button(app, "발송").disabled
        finally:
            api.set_client(None)
    with TestClient(make_server()) as c:
        api.set_client(c)
        try:
            app = open_marketing(login())
            assert any("발송 대상이 없습니다" in w.value for w in app.warning) and button(app, "발송").disabled
        finally:
            api.set_client(None)


def test_admin_can_opt_out_member_and_excludes_from_targets(server):
    add_member(server, "가"); add_member(server, "나")
    app = open_marketing(login())
    app.multiselect[0].set_value(["신규"]).run()
    button(app, "수신거부로 등록").click().run()
    app.multiselect[0].set_value(["신규"]).run()
    assert any("발송 대상 1명" in c.value for c in app.caption)
