"""수용: 오늘 주문 카드가 API 집계값을 표시하고 새로고침에 반응하는지 확인한다."""

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

from app.core.settings import Settings
from app.factory import create_app
from shared import api


@pytest.fixture
def server():
    config = Settings(database_url="sqlite:///:memory:", app_env="dev", jwt_secret="x" * 32,
                      admin_token="admin-secret", _env_file=None)
    with TestClient(create_app(config)) as client:
        # 서버가 처음 뜰 때 기본 메뉴가 들어가므로, 빈 DB를 전제로 한 이 테스트들을 위해 메뉴를 비운다.
        client.app.state.db.run("DELETE FROM menus")
        api.set_client(client)
        try:
            yield client
        finally:
            api.set_client(None)


def open_dashboard(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "api")
    screen = AppTest.from_file(str(ROOT / "admin/app.py"), default_timeout=30).run()
    screen.text_input[0].set_value("admin-secret")
    screen.button[0].click().run()
    assert not screen.exception
    return screen


def displayed_today_orders(screen):
    # 카드 라벨에 연결된 값만 읽어 다른 카드의 숫자와 혼동하지 않는다.
    html = "\n".join(element.value for element in screen.get("html"))
    match = re.search(r'class="k">오늘 주문</div><div class="v">(\d+)', html)
    assert match, "오늘 주문 카드가 표시되지 않았습니다."
    return int(match.group(1))


def test_today_order_card_uses_database_and_refreshes(server, monkeypatch):
    now = datetime.now(timezone.utc)
    for created_at in (now, now - timedelta(days=1)):
        server.app.state.db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                                (1, 10000, created_at.isoformat()))
    screen = open_dashboard(monkeypatch)
    assert displayed_today_orders(screen) == 1
    server.app.state.db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                            (2, 20000, now.isoformat()))
    screen.button(key="dashboard_refresh").click().run()
    assert not screen.exception
    assert displayed_today_orders(screen) == 2


def test_today_order_card_shows_zero_even_without_order_history(server, monkeypatch):
    # 주문 목록 자체가 비어 있을 때도 빈 화면 안내와 0건 카드를 함께 표시해야 한다.
    from app import dummy

    monkeypatch.setattr(dummy, "orders", lambda: [])
    screen = open_dashboard(monkeypatch)
    assert displayed_today_orders(screen) == 0
    assert any("아직 주문이 없어요." in element.value for element in screen.get("html"))


def test_basic_stat_cards_use_db_values_across_dashboard_tabs(server, monkeypatch):
    # 서버 더미의 숫자가 아닌 준비한 DB 기록이 각 하위 화면에 표시되는지 확인한다.
    db = server.app.state.db
    member = server.app.state.members.upsert_login("stats-screen", "통계 회원", birth_year=2000, gender="male")
    order = db.run("INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?, ?, ?, ?, ?)",
                   (1, member["id"], 12345, True, datetime.now(timezone.utc).isoformat()))
    db.run("INSERT INTO order_items (order_id, name, unit_price, qty) VALUES (?, ?, ?, ?)",
           (order, "DB 전용 메뉴", 12345, 3))
    for _ in range(4):
        db.run("INSERT INTO recommendation_events (table_no) VALUES (?)", (1,))
    screen = open_dashboard(monkeypatch)
    html = "\n".join(element.value for element in screen.get("html"))
    assert '평균 주문금액</div><div class="v">12,345' in html
    assert '오늘 신규 고객</div><div class="v">1' in html
    assert '오늘 재방문 고객</div><div class="v">0' in html
    assert "DB 전용 메뉴" in html
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("메뉴").run()
    assert not screen.exception
    html = "\n".join(element.value for element in screen.get("html"))
    assert 'AI 추천 적중률</div><div class="v">25%' in html
    assert '추천 노출</div><div class="v">4' in html
    assert "전체 AI 조합이 포함된 주문 수 / 전체 추천 노출 횟수" in html
