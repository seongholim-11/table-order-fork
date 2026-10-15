"""user 페이지(Streamlit AppTest) ↔ 실제 백엔드(FastAPI TestClient) QR 로그인 통합 테스트.

휴대폰 동작은 같은 TestClient 로 흉내 낸다 (QR 주소 열기 → 모의 카카오 로그인 콜백).
실행: 저장소 루트에서 `python -m pytest tests -q` (fastapi, streamlit 필요)
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "user")]

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.core.settings import Settings
from app.factory import create_app
from shared import api

APP = str(ROOT / "user" / "app.py")


@pytest.fixture
def server():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None)
    with TestClient(create_app(s)) as c:
        api.set_client(c)
        yield c
    api.set_client(None)


def phone_login(server, qr_url: str, nickname: str, agree: bool = False, expect: int = 200):
    """휴대폰이 QR을 스캔하고 (모의) 카카오 로그인을 마치는 과정."""
    path = urlparse(qr_url)
    state = path.query.removeprefix("token=")
    assert server.get(f"{path.path}?{path.query}").status_code == 200  # 광고성 문자 수신 동의 화면
    r = server.get("/api/auth/kakao/continue", params={"token": state, **({"agree": "1"} if agree else {})},
                   follow_redirects=False)
    assert r.status_code == 302
    r = server.get("/api/auth/kakao/callback", params={"state": state, "code": f"mock-{nickname}"})
    assert r.status_code == expect
    return r


def ss(app):
    return app.session_state


def test_guest_sees_guest_order_button_and_roulette_asks_for_login(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert app.button(key="start_btn").label == "🍴 비회원 주문  ›"
    assert not ss(app)["members"] and any("로그인 후 룰렛" in h.value for h in app.get("html"))
    app.button(key="roulette_btn").click().run()  # 로그인 안 한 상태로 START → 로그인 팝업
    assert ss(app)["roulette"] is None
    login = ss(app)["login"]
    assert login and login["qr_url"].startswith("http://t/api/auth/kakao/start?token=")
    assert not app.exception


def test_login_then_spin_then_second_spin_needs_another_login(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key="roulette_btn").click().run()
    phone_login(server, ss(app)["login"]["qr_url"], "가")
    app.run()  # 팝업이 닫힌 뒤에도 완료된 로그인이 반영된다
    assert ss(app)["member"]["nickname"] == "가" and ss(app)["login"] is None
    assert app.button(key="start_btn").label == "🍴 회원 주문  ›"
    assert len(ss(app)["members"]) == 1 and any("룰렛 기회 1회" in h.value for h in app.get("html"))

    app.button(key="roulette_btn").click().run()  # 로그인 O → 룰렛이 돈다
    assert ss(app)["roulette"] and ss(app)["members"][0]["prize"]
    assert ss(app)["login"] is None and not [d for d in app.get("dialog")]  # 돌린 직후에는 로그인 팝업이 없다
    first_result = ss(app)["roulette"]["idx"]

    app.button(key="roulette_btn").click().run()  # 이미 돌렸는데 또 돌리려 하면 → 추가 로그인 팝업
    assert ss(app)["roulette"]["idx"] == first_result and ss(app)["login"]
    phone_login(server, ss(app)["login"]["qr_url"], "나")
    app.run()
    assert [m["nickname"] for m in ss(app)["members"]] == ["가", "나"] and ss(app)["members"][1]["prize"] is None
    app.button(key="roulette_btn").click().run()
    assert ss(app)["members"][1]["prize"] and ss(app)["login"] is None and not app.exception
    # 하단에 로그인한 회원이 누적된다
    log = next(h.value for h in app.get("html") if "mlog" in h.value)
    assert "가님" in log and "나님" in log and "로그인한 회원 <span>2</span>" in log


def test_same_member_cannot_log_in_again_on_same_tablet(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key="login_open").click().run()
    phone_login(server, ss(app)["login"]["qr_url"], "같은사람")
    app.run()
    assert len(ss(app)["members"]) == 1
    app.button(key="login_open").click().run()
    r = phone_login(server, ss(app)["login"]["qr_url"], "같은사람", expect=409)  # 이미 로그인한 회원은 거절
    assert "이미 로그인" in r.text
    app.run()
    rows = ss(app)["members"]
    assert len(rows) == 1 and rows[0]["eligible"] is True and ss(app)["login"]  # 기록은 그대로, 팝업은 열려 있음
    assert server.get(f"/api/auth/qr/{ss(app)['login']['secret']}").json()["status"] == "rejected"
    assert server.get("/api/members/me", headers={"Authorization": f"Bearer {ss(app)['access_token']}"}).json()["visit_count"] == 1
    # 다른 회원은 로그인할 수 있다
    ss(app)["login"]["created"] -= 10_000  # 새 QR 받기 (재생성 버튼과 같은 효과)
    app.button(key="login_open").click().run()
    phone_login(server, ss(app)["login"]["qr_url"], "다른사람")
    app.run()
    assert [m["nickname"] for m in ss(app)["members"]] == ["같은사람", "다른사람"]


def test_no_profile_form_and_consent_comes_from_phone_login(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key="login_open").click().run()
    phone_login(server, ss(app)["login"]["qr_url"], "홍대손님", agree=True)
    app.run()
    assert not app.text_input and not app.checkbox and not app.exception  # 회원 정보 입력 UI 없음
    assert not any("회원 정보 입력" in e.label for e in app.expander)
    me = server.get("/api/members/me", headers={"Authorization": f"Bearer {ss(app)['access_token']}"}).json()
    assert me["marketing_consent"] is True


def test_used_qr_is_rejected_and_expired_qr_can_be_refreshed(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key="login_open").click().run()
    first = ss(app)["login"]
    phone_login(server, first["qr_url"], "가")
    path = urlparse(first["qr_url"])
    assert server.get(f"{path.path}?{path.query}", follow_redirects=False).status_code == 410  # 재사용 불가
    app.run()
    app.button(key="login_open").click().run()
    old = ss(app)["login"]["token"]
    ss(app)["login"]["created"] -= 10_000  # 만료시키기
    app.run()
    app.button(key="login_open").click().run()  # 만료된 QR 은 열 때 새로 발급
    assert ss(app)["login"]["token"] != old


def test_without_server_roulette_explains_and_guest_order_still_works():
    api.set_client(__import__("httpx").Client(base_url="http://127.0.0.1:9", timeout=1))
    try:
        app = AppTest.from_file(APP, default_timeout=30)
        app.query_params["table"] = "7"
        app.run()
        assert not app.exception and ss(app)["table"] == 7
        app.button(key="roulette_btn").click().run()
        assert any("서버에 연결할 수 없어요" in h.value for h in app.get("html")) and not ss(app)["members"]
        app.button(key="start_btn").click().run()  # 비회원 주문은 서버 없이도 가능
        assert not app.exception
    finally:
        api.set_client(None)


def test_order_screen_and_category_are_restored_from_url_on_reload():
    api.set_client(__import__("httpx").Client(base_url="http://127.0.0.1:9", timeout=1))
    try:
        app = AppTest.from_file(APP, default_timeout=30)
        app.query_params["table"] = "7"
        app.run()
        assert app.session_state["page"] == "splash" and "page" not in app.query_params
        app.button(key="start_btn").click().run()
        app.button(key="cat_soup").click().run()
        assert app.query_params["page"] == "order" and app.query_params["cat"] == "soup"
        fresh = AppTest.from_file(APP, default_timeout=30)  # 새로고침
        fresh.query_params["table"], fresh.query_params["page"], fresh.query_params["cat"] = "7", "order", "soup"
        fresh.run()
        assert not fresh.exception
        assert fresh.session_state["page"] == "order" and fresh.session_state["cat"] == "soup"
    finally:
        api.set_client(None)
