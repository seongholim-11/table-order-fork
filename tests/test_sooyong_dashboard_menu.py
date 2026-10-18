"""메뉴 하위 화면의 중복 제거와 실제 DB 표시·북마크 호환을 검증한다."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import admin_repository as ar
from test_sooyong_today_orders import open_dashboard, server


def html_of(screen):
    return "\n".join(element.value for element in screen.get("html"))


def add_soldout_menu(server):
    """더미 목록에는 없는 이름으로 DB와 화면의 실제 연결을 구분한다."""
    db = server.app.state.db
    db.run("INSERT INTO menus (id, category_id, name, price, is_soldout) VALUES (?, ?, ?, ?, ?)",
           ("db-stock", "anju", "DB 전용 품절 메뉴", 12345, True))
    order = db.run("INSERT INTO orders (table_no, total, ai_combo, created_at) VALUES (?, ?, ?, ?)",
                   (7, 12345, True, datetime.now(timezone.utc).isoformat()))
    db.run("INSERT INTO order_items (order_id, menu_id, name, unit_price, qty) VALUES (?, ?, ?, ?, ?)",
           (order, "db-stock", "DB 전용 품절 메뉴", 12345, 2))


def test_menu_screen_uses_db_and_has_no_duplicate_customer_cards(server, monkeypatch):
    add_soldout_menu(server)
    screen = open_dashboard(monkeypatch)
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("메뉴").run()
    assert not screen.exception
    assert "메뉴 · 운영" not in screen.sidebar.radio(key="nav_sub_대시보드").options
    html = html_of(screen)
    assert "인기 메뉴 TOP 10" in html and "메뉴 판매 현황" in html and "DB 전용 품절 메뉴" in html
    assert '품절 메뉴</div><div class="v">1' in html
    assert '품절된 인기 메뉴</div><div class="v">1' in html
    assert 'AI 추천 주문 객단가</div><div class="v">12,345' in html
    assert '일반 주문 객단가</div><div class="v">-' in html
    assert all(label not in html for label in ("전체 회원", "휴면 고객", "문자 수신 가능", "고객 관리 · 운영 알림"))
    server.app.state.db.run("UPDATE menus SET is_soldout=? WHERE id=?", (False, "db-stock"))
    screen.button(key="dashboard_refresh").click().run()
    assert not screen.exception
    assert '품절 메뉴</div><div class="v">0' in html_of(screen)
    assert '품절된 인기 메뉴</div><div class="v">0' in html_of(screen)
    # 고객 등급의 목록·등급 카드는 원래 위치에 계속 남아 있어야 한다.
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert not screen.exception and len(screen.dataframe) == 1
    assert all(f"{grade} 고객" in html_of(screen) for grade in ar.GRADES)


def test_menu_stock_does_not_use_dummy_menu_or_customer_repository(server, monkeypatch):
    add_soldout_menu(server)
    screen = open_dashboard(monkeypatch)

    def unexpected_read(*args, **kwargs):
        pytest.fail("메뉴 화면이 더미 메뉴 또는 중복 고객 데이터를 조회했습니다.")

    # 각 리런에서 모듈을 다시 읽지 않도록 현재 로딩 시점을 명시한다.
    ar._loaded_mtime = Path(ar.__file__).stat().st_mtime
    monkeypatch.setattr(ar.AdminRepository, "menus", unexpected_read)
    monkeypatch.setattr(ar.AdminRepository, "members", unexpected_read)
    monkeypatch.setattr(ar.AdminRepository, "customer_grades", unexpected_read)
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("메뉴").run()
    assert not screen.exception and "DB 전용 품절 메뉴" in html_of(screen)


def test_empty_db_menu_screen_does_not_show_dummy_stock(server, monkeypatch):
    screen = open_dashboard(monkeypatch)
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("메뉴").run()
    assert not screen.exception
    html = html_of(screen)
    assert '품절 메뉴</div><div class="v">0' in html and "노가리 구이" not in html


@pytest.mark.parametrize("tab", ["메뉴", "메뉴 · 운영"])
def test_new_and_old_bookmarks_open_menu_in_dummy_mode(monkeypatch, tab):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    screen = AppTest.from_file(str(ROOT / "admin/app.py"), default_timeout=30)
    screen.query_params.update(page="대시보드", tab=tab)
    screen.run()
    screen.text_input[0].set_value("change-me")
    screen.button[0].click().run()
    assert not screen.exception
    assert screen.sidebar.radio(key="nav_sub_대시보드").value == "메뉴"
    assert screen.query_params["tab"] == "메뉴" and "메뉴 판매 현황" in html_of(screen)
    assert "노가리 구이" in html_of(screen)
