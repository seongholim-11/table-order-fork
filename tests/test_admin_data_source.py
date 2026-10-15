"""관리자 화면의 데이터 소스 전환(DATA_SOURCE=dummy|api|auto)과 더미/서버 JSON 계약 테스트."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

import admin_repository as ar
from admin_dummy_data import DummyBackend, Unsupported
from app.core.settings import Settings
from app.factory import create_app
from app.services.grades import KST
from shared import api

APP = str(ROOT / "admin" / "app.py")
PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]
RULE = ar.DEFAULT_RULE



def go_page(app, page):
    """사이드바에서 메뉴를 연다 (주문 이력·마케팅은 하위 메뉴의 첫 항목)."""
    if page in {"주문 이력": 0, "마케팅": 0}:
        sub = {"주문 이력": "전체 주문", "마케팅": "AI 문자"}[page]
        return app.sidebar.radio(key=f"nav_sub_{page}").set_value(sub).run()
    return app.sidebar.radio(key="nav_top").set_value(page).run()

def make_server(**kw):
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", store_branch="서버지점", _env_file=None, **kw)
    return create_app(s, sms_clock=lambda: datetime(2026, 10, 12, 14, 0, tzinfo=KST))


def set_profile(c, h, **cols):
    """카카오에서 받아 오는 값과 수신 동의를 테스트용으로 직접 채운다."""
    members = c.app.state.members
    mid = c.get("/api/members/me", headers=h).json()["id"]
    consent = cols.pop("marketing_consent", None)
    for col, val in cols.items():
        members.db.run(f"UPDATE members SET {col}=? WHERE id=?", (val, mid))
    if consent is not None:
        members.set_marketing_consent(mid, consent)


def seed_member_and_order(c):
    consent = True
    q = c.post("/api/auth/qr", json={"table_no": 1}).json()
    c.get(f"/api/auth/kakao/start?token={q['token']}")
    c.get("/api/auth/kakao/continue", params={"token": q["token"], "agree": "1" if consent else ""}, follow_redirects=False)
    c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-계약"})
    h = {"Authorization": f"Bearer {c.get(f'/api/auth/qr/{q['secret']}').json()['access_token']}"}
    set_profile(c, h, birth_year=1995, gender="female", phone="010-1234-5678")
    line = {"id": "c1", "name": "통닭", "opt": "", "unit": 18000, "qty": 1}
    c.post("/api/orders", headers=h, json={"table_no": 3, "lines": [line], "total": 18000})


@pytest.fixture
def server():
    with TestClient(make_server()) as c:
        seed_member_and_order(c)
        api.set_client(c)
        yield c
    api.set_client(None)


@pytest.fixture
def dead_server():
    api.set_client(httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    yield
    api.set_client(None)


def _unknown_kinds(node, out):
    if type(node).__name__ == "UnknownElement":
        out.append(type(node.proto).__name__)
    for child in getattr(node, "children", {}).values():
        _unknown_kinds(child, out)
    return out


def assert_clean(app, page):
    """오류가 없어야 하고, Streamlit 'magic' 이 객체를 화면에 그려 넣는 일(Help/DocString 요소)도 없어야 한다.

    예: `st.bar_chart(a) if x else st.write(b)` 처럼 표현식 결과가 버려지지 않으면 DeltaGenerator 설명이 화면에 나온다.
    """
    assert not app.exception, page
    leaked = [k for k in _unknown_kinds(app.main, []) if k in ("Help", "DocString")]
    assert not leaked, f"{page}: 화면에 객체 설명이 그려졌어요 {leaked}"


def keys(x):
    return set(x[0].keys()) if isinstance(x, list) else set(x.keys())


# ---- 계약: 더미와 서버가 같은 모양의 JSON 을 돌려준다 -------------------------------------------------------
def test_dummy_backend_returns_the_same_json_shape_as_the_server(server):
    dummy, real = DummyBackend(), ar.ApiBackend("admin-secret")
    assert real.login("admin-secret")
    assert keys(dummy.store()) == keys(real.store())
    d, r = dummy.menus(), real.menus()
    assert keys(d) == keys(r)
    assert keys(d["menus"]) == keys(r["menus"]) and keys(d["categories"]) == keys(r["categories"])
    assert keys(dummy.members(RULE)) == keys(real.members(RULE))
    assert keys(dummy.members(RULE)["members"]) == keys(real.members(RULE)["members"])
    d_orders, r_orders = dummy.orders(), real.orders()
    assert keys(d_orders) == keys(r_orders) and keys(d_orders[0]["lines"]) == keys(r_orders[0]["lines"])
    ds, rs = dummy.stats(RULE), real.stats(RULE)
    assert keys(ds) == keys(rs) and keys(ds["ai"]) == keys(rs["ai"])


def test_repository_tables_have_identical_columns_for_dummy_and_server(server):
    dummy = ar.AdminRepository(DummyBackend())
    real = ar.AdminRepository(ar.ApiBackend("admin-secret"))
    assert list(dummy.menus().columns) == list(real.menus().columns) == ar.MENU_COLUMNS
    assert list(dummy.members().columns) == list(real.members().columns)
    assert list(dummy.orders().columns) == list(real.orders().columns)
    row = real.orders().iloc[0]
    assert row["닉네임"] == "계약" and row["테이블"] == 3 and "통닭 x1" in row["주문 내역"]


def test_dummy_schedule_and_cancel_restores_usage():
    from datetime import datetime, timedelta
    repo = ar.AdminRepository(DummyBackend())
    base = repo.sms_usage()["used"]["SMS"]
    when = datetime.now() + timedelta(days=1)
    r = repo.sms_send(["휴면"], "예약 문자", when)
    assert r["scheduled_at"] and repo.sms_usage()["used"]["SMS"] == base + r["count"]
    log = repo.sms_logs()[0]
    assert log["status"] == "scheduled"
    assert repo.sms_cancel(log["id"])["status"] == "canceled" and repo.sms_usage()["used"]["SMS"] == base
    assert not repo.sms_preview(["휴면"], "x", datetime.now())["ok"]  # 10분 이내 예약 거절


def test_dummy_marketing_works_like_the_server_without_sending_anything():
    repo = ar.AdminRepository(DummyBackend())
    usage = repo.sms_usage()
    assert set(usage) == {"month", "used", "limit"} and usage["used"]["SMS"] > 0 and repo.sms_logs()
    plan = repo.sms_preview(["휴면"], "안녕하세요")
    assert plan["ok"] and plan["dry_run"] and plan["type"] == "SMS" and plan["targets"] > 0
    assert not repo.sms_preview(["휴면"], "  ")["ok"]  # 빈 본문
    before = len(repo.sms_logs())
    result = repo.sms_send(["휴면"], "안녕하세요")
    assert result["dry_run"] and result["count"] == plan["targets"]
    assert len(repo.sms_logs()) == before + 1 and repo.sms_usage()["used"]["SMS"] == usage["used"]["SMS"] + plan["targets"]


def test_dummy_opt_out_removes_member_from_targets():
    repo = ar.AdminRepository(DummyBackend())
    members = repo.members()
    pick = members[members["마케팅 수신 동의"] & ~members["수신거부"] & (members["등급"] == "휴면")].iloc[0]
    before = repo.sms_preview(["휴면"], "x")["targets"]
    repo.opt_out(int(pick["customer_id"]))
    assert repo.sms_preview(["휴면"], "x")["targets"] == before - 1


# ---- 저장: 표에서 바뀐 것만 서버에 반영 ---------------------------------------------------------------------
def test_save_menus_sends_only_changed_rows_new_rows_and_deletions(server):
    repo = ar.AdminRepository(ar.ApiBackend("admin-secret"))
    old = repo.menus()
    new = old.copy()
    new.loc[new["id"] == "c2", "가격"] = 21000
    new.loc[new["id"] == "c2", "추천 가중치"] = 80
    new.loc[new["id"] == "c3", "판매 여부"] = False
    new = new[new["id"] != "a1"]  # 삭제
    added = pd.DataFrame([{"id": None, "메뉴명": "신메뉴", "카테고리": "안주", "가격": 9000, "설명": None, "이미지 URL": None,
                           "판매 여부": True, "매운 정도": "보통맛", "추천 가중치": 60, "세트 가능": True}])
    new = pd.concat([new, added], ignore_index=True)  # 데이터 편집기가 새 행을 붙이는 방식과 같다
    assert repo.save_menus(new, old) == {"saved": 3, "deleted": 1}
    after = {m["id"]: m for m in server.get("/api/menus").json()}
    assert after["c2"]["price"] == 21000 and after["c2"]["weight"] == 80 and after["c3"]["soldout"] is True
    assert "a1" not in after
    created = next(m for m in after.values() if m["name"] == "신메뉴")
    assert created["cat"] == "anju" and created["spicy"] == 2 and created["weight"] == 60
    assert repo.save_menus(repo.menus(), repo.menus()) == {"saved": 0, "deleted": 0}  # 바뀐 게 없으면 호출 없음


def test_dummy_backend_save_menus_works_in_memory():
    repo = ar.AdminRepository(DummyBackend())
    old = repo.menus()
    new = old.copy()
    new.loc[new["id"] == "c1", "가격"] = 1234
    assert repo.save_menus(new, old) == {"saved": 1, "deleted": 0}
    assert int(repo.menus().set_index("id").at["c1", "가격"]) == 1234


# ---- 화면: 소스별 로그인과 전체 페이지 ------------------------------------------------------------------------
def login(monkeypatch, mode, token="admin-secret"):
    monkeypatch.setenv("DATA_SOURCE", mode)
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value(token)
    app.button[0].click().run()
    return app


def test_every_page_renders_in_dummy_mode_even_with_server_up(server, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = login(monkeypatch, "dummy", "change-me")
    assert app.session_state["repo"].source == "dummy" and not app.exception
    assert any("더미 데이터" in c.value for c in app.sidebar.caption)
    for page in PAGES:
        go_page(app, page)
        assert_clean(app, page)
    assert any("더미 데이터로 만든 화면" in c.value for c in app.caption)  # 마케팅도 더미로 동작


def test_every_page_renders_in_api_mode_with_real_data(server, monkeypatch):
    app = login(monkeypatch, "api")
    assert app.session_state["repo"].source == "api" and any("서버 데이터" in c.value for c in app.sidebar.caption)
    assert any("서버지점" in c.value for c in app.sidebar.caption)
    for page in PAGES:
        go_page(app, page)
        assert_clean(app, page)


def test_auto_mode_uses_api_when_up_and_dummy_with_notice_when_down(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    with TestClient(make_server()) as c:
        api.set_client(c)
        try:
            assert login(monkeypatch, "auto").session_state["repo"].source == "api"
        finally:
            api.set_client(None)
    api.set_client(httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    try:
        app = login(monkeypatch, "auto", "change-me")
        assert app.session_state["repo"].source == "dummy" and any("더미 데이터로 표시" in w.value for w in app.warning)
        assert not login(monkeypatch, "auto", "wrong").session_state["owner"]
    finally:
        api.set_client(None)


def test_wrong_token_is_rejected_in_every_mode(server, monkeypatch):
    for mode in ("api", "dummy", "auto"):
        app = login(monkeypatch, mode, "wrong")
        assert app.error and not app.session_state["owner"], mode


def test_marketing_screen_in_dummy_mode_can_preview_and_send(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = login(monkeypatch, "dummy", "change-me")
    app.sidebar.radio(key="nav_sub_마케팅").set_value("AI 문자").run()
    assert not app.exception and any("더미 데이터로 만든 화면" in c.value for c in app.caption)
    assert any("발송 대상" in c.value for c in app.caption)  # 기본값(휴면)으로 바로 미리보기
    before = len(app.session_state["repo"].sms_logs())
    next(b for b in app.button if b.label == "발송").click().run()
    assert not app.exception and len(app.session_state["repo"].sms_logs()) == before + 1
    assert any("발송 내역" in h.value for h in app.get("html"))
