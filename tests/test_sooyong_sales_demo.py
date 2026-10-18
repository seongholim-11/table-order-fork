"""고객 매출 순위 제거와 실제 DB 상승률 표시·새로고침을 함께 확인한다."""

import sys
from datetime import datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

from app.services.grades import KST
from app.stores.sales_demo import seed_sales_demo
from app.stores.sales_demo import DEMO_LABEL, rebalance_sales_demo_tables
from test_sooyong_today_orders import open_dashboard, server


def test_removed_customer_ranking_and_red_blue_changes_across_tabs(server, monkeypatch):
    db = server.app.state.db
    for menu_id, category, price in (("fish", "anju", 14000), ("egg", "anju", 16000),
                                      ("beer", "beer", 5000), ("cola", "drink", 3000)):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
               (menu_id, category, menu_id, price))
    today = datetime.now(KST).date()
    for day, total in ((today, 40000), (today - timedelta(days=7), 80000),
                       (today - timedelta(days=8), 100000)):
        stamp = datetime.combine(day, time.min, tzinfo=KST).isoformat()
        db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (1, total, stamp))
    expected = seed_sales_demo(db, today, apply=True)["after"]
    screen = open_dashboard(monkeypatch)
    # 실제 DB→API→화면에서 완만한 상승·하락과 각각의 색상 클래스를 함께 확인한다.
    assert .03 <= expected["last_day_change"] <= .18 and -.15 <= expected["week_change"] <= -.01
    day_delta = f'<div class="s up">▲ {expected["last_day_change"]:.0%} (지난주 같은 요일 대비)</div>'
    week_delta = f'<div class="s down">▼ {abs(expected["week_change"]):.0%} (지난 7일 대비)</div>'
    for tab in ("한눈에 보기", "오늘 · 매출", "매출 추이", "고객 분석", "메뉴"):
        screen.sidebar.radio(key="nav_sub_대시보드").set_value(tab).run()
        assert not screen.exception
        html = "\n".join(element.value for element in screen.get("html"))
        assert all(title not in html for title in ("고객별 주문금액 TOP 5", "마지막 영업일 매출 TOP 5",
                                                   "상위 고객 주문금액 비중", "상위 5팀 매출 비중"))
        if tab in ("한눈에 보기", "오늘 · 매출", "매출 추이"):
            assert day_delta in html and week_delta in html
            assert f'{expected["last_day_revenue"]:,}' in html
            assert f'{expected["week_revenue"]:,}' in html
        if tab in ("한눈에 보기", "고객 분석"):
            assert "회원 매출 비중" in html and "주문 테이블 TOP 5" in html
    screen.sidebar.radio(key="nav_sub_대시보드").set_value("한눈에 보기").run()
    screen.button(key="dashboard_refresh").click().run()
    assert not screen.exception
    assert day_delta in "\n".join(element.value for element in screen.get("html"))


def test_table_top_five_follows_database_counts_with_same_revenue(server, monkeypatch):
    """화면에 순위를 고정하지 않고 DB 주문 건수 내림차순과 새로고침을 확인한다."""
    db = server.app.state.db
    for menu_id, price in (("fish", 14000), ("beer", 5000), ("cola", 3000)):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, price))
    stamp = datetime.now(KST).replace(hour=17, minute=0, second=0, microsecond=0).isoformat()
    for index in range(20):
        order = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (index + 1, 22000, stamp))
        for menu_id, price in (("fish", 14000), ("beer", 5000), ("cola", 3000)):
            db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, option_label) VALUES (?, ?, ?, ?, ?, ?)",
                   (order, menu_id, menu_id, 1, price, DEMO_LABEL))
    rebalance_sales_demo_tables(db, apply=True)
    screen = open_dashboard(monkeypatch)
    for tab in ("한눈에 보기", "고객 분석"):
        screen.sidebar.radio(key="nav_sub_대시보드").set_value(tab).run()
        assert not screen.exception
        html = "\n".join(element.value for element in screen.get("html"))
        start = html.index("마지막 영업일 주문 테이블 TOP 5")
        ranking = html[start:html.index('</div></div>', start)]
        assert [ranking.index(f'>{table}번</span>') for table in (7, 12, 3, 9, 14)] == sorted(
            ranking.index(f'>{table}번</span>') for table in (7, 12, 3, 9, 14))
        assert all(f'>{count}건</span>' in ranking for count in (6, 5, 4, 3, 2))
        if tab == "한눈에 보기":
            assert '마지막 영업일 매출</div><div class="v">440,000' in html
    screen.button(key="dashboard_refresh").click().run()
    assert not screen.exception
