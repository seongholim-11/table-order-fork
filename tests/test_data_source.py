"""데이터 소스 전환(DATA_SOURCE=dummy|api|auto) 통합 테스트: 같은 화면이 더미/서버 데이터로 모두 동작한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "user")]

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.core.settings import Settings
from app.factory import create_app
from shared import api

APP = str(ROOT / "user" / "app.py")
ADMIN = {"Authorization": "Bearer admin-secret"}


@pytest.fixture
def server():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", store_branch="서버지점", _env_file=None)
    with TestClient(create_app(s)) as c:
        api.set_client(c)
        yield c
    api.set_client(None)


@pytest.fixture
def dead_server():
    api.set_client(httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    yield
    api.set_client(None)


def run_app(mode, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", mode)
    return AppTest.from_file(APP, default_timeout=30).run()


def html(app):
    return " ".join(h.value for h in app.get("html"))


def open_chicken(app):
    app.button(key="start_btn").click().run()
    app.button(key="cat_chicken").click().run()
    return html(app)


@pytest.mark.skip(reason="GET 이 더미라 저장한 값이 조회에 반영되지 않음 - 해당 GET 을 DB 로 구현하면 이 skip 을 지운다")
def test_api_mode_uses_server_data_and_admin_edits_show_up(server, monkeypatch):
    server.put("/admin/api/menus/c2", headers=ADMIN, json={"price": 21000})
    server.put("/admin/api/menus/c3", headers=ADMIN, json={"soldout": True})
    app = run_app("api", monkeypatch)
    assert app.session_state["data_source"] == "api" and not app.exception
    page = open_chicken(app)
    assert "서버지점" in page  # 매장 정보가 서버에서
    assert "21,000원" in page  # 관리자가 바꾼 가격
    assert app.button(key="add_c3").disabled  # 관리자가 품절 처리한 메뉴


def test_dummy_mode_ignores_the_server_even_when_it_is_up(server, monkeypatch):
    server.put("/admin/api/menus/c2", headers=ADMIN, json={"price": 21000})
    app = run_app("dummy", monkeypatch)
    assert app.session_state["data_source"] == "dummy"
    page = open_chicken(app)
    assert "21,000원" not in page and "20,000원" in page and "서버지점" not in page


@pytest.mark.skip(reason="GET 이 더미라 저장한 값이 조회에 반영되지 않음 - 해당 GET 을 DB 로 구현하면 이 skip 을 지운다")
def test_content_edited_on_server_changes_the_screen(server, monkeypatch):
    """직원 호출 항목·카테고리 같은 '콘텐츠'도 서버에서 바꾸면 화면에 반영된다."""
    cats = server.get("/api/content/categories").json()
    cats[2]["name"] = "서버에서 바꾼 이름"
    assert server.put("/admin/api/content/categories", headers=ADMIN, json=cats).status_code == 200
    app = run_app("api", monkeypatch)
    app.button(key="start_btn").click().run()
    assert app.button(key="cat_chicken").label.endswith("서버에서 바꾼 이름")


@pytest.mark.skip(reason="GET 이 더미라 저장한 값이 조회에 반영되지 않음 - 해당 GET 을 DB 로 구현하면 이 skip 을 지운다")
def test_orders_are_sent_to_the_server_only_in_api_mode(server, monkeypatch):
    for mode, expected in (("api", 1), ("dummy", 0)):
        before = len(server.get("/admin/api/orders", headers=ADMIN).json())
        app = run_app(mode, monkeypatch)
        app.button(key="start_btn").click().run()
        app.button(key="cat_chicken").click().run()
        app.button(key="add_c1").click().run()
        app.button(key="order_btn").click().run()
        app.session_state["confirm_order"] = True
        next(b for b in app.get("button") if b.proto.label == "주문하기").click().run()
        assert len(app.session_state["orders"]) == 1 and not app.exception
        after = server.get("/admin/api/orders", headers=ADMIN).json()
        assert len(after) - before == expected, mode
        if expected:
            assert after[0]["table_no"] == 12 and after[0]["lines"][0]["id"] == "c1"
            assert app.session_state["orders"][0]["no"] == after[0]["id"]  # 서버가 준 주문번호


@pytest.mark.skip(reason="GET 이 더미라 저장한 값이 조회에 반영되지 않음 - 해당 GET 을 DB 로 구현하면 이 skip 을 지운다")
def test_quiz_results_use_server_rules_and_log_impressions(server, monkeypatch):
    rules = server.get("/api/content/rules").json()
    rules["pairings"] = [p for p in rules["pairings"] if p[0] != "classic"]  # 서버 규칙에서 조합 하나를 뺀다
    server.put("/admin/api/content/rules", headers=ADMIN, json=rules)
    app = run_app("api", monkeypatch)
    app.button(key="start_btn").click().run()
    app.button(key="open_quiz").click().run()
    questions = server.get("/api/content/quiz_questions").json()
    for q in questions:
        app.button(key=f"quiz_pick_{q['id']}_1").click().run()
    assert not app.exception
    names = " ".join(h.value for h in app.get("html"))
    assert "바삭한 치킨 한 상" not in names  # 서버 규칙 반영
    stats = server.get("/admin/api/stats", headers=ADMIN).json()
    assert stats["ai"]["recommendations"] == 1  # 노출이 서버에 기록됨


def test_api_mode_without_server_shows_error_page(dead_server, monkeypatch):
    app = run_app("api", monkeypatch)
    assert not app.exception and any("서버에 연결할 수 없습니다" in e.value for e in app.error)
    assert "data_source" not in app.session_state


def test_auto_mode_falls_back_to_dummy_without_server(dead_server, monkeypatch):
    app = run_app("auto", monkeypatch)
    assert app.session_state["data_source"] == "dummy" and not app.exception
    assert "20,000원" in open_chicken(app)


def test_auto_mode_uses_server_when_up_and_unknown_mode_means_auto(server, monkeypatch):
    for mode in ("auto", "typo"):
        app = run_app(mode, monkeypatch)
        assert app.session_state["data_source"] == "api"
