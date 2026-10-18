"""수용 3번: 화면 원본과 서버 계산을 비교하고 실제 DB가 그래프에 표시되는지 확인한다."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import admin_repository as ar
from app.services.grades import KST, grade_of
from app.services.stats import sales_insights
from dashboard_stats import summarize
from test_sooyong_today_orders import open_dashboard, server


@pytest.mark.parametrize("guest_only", [False, True])
def test_server_matches_original_screen_calculation(guest_only):
    # 다양한 날짜·가격·회원·AI 조합을 같은 자료로 계산해 함수 이식 때의 누락을 찾는다.
    last = datetime(2026, 10, 16, 23, tzinfo=KST)
    members = [] if guest_only else [{"id": 1, "visit_count": 5, "last_visit_at": last.isoformat()}]
    orders = []
    for index in range(87):
        at = last - timedelta(days=index % 41, hours=index % 4)
        orders.append({"id": index + 1, "table_no": index % 5 + 1,
                       "member_id": 1 if members and index % 3 else None, "nickname": "통계 회원",
                       "total": index * 987, "ai_combo": index % 4 == 0, "ts": at.astimezone(timezone.utc).isoformat()})
    frame = pd.DataFrame([{"주문 시각": datetime.fromisoformat(order["ts"]).astimezone(KST).replace(tzinfo=None),
                           "테이블": order["table_no"], "customer_id": order["member_id"], "닉네임": order["nickname"],
                           "금액": order["total"], "AI 추천 사용": order["ai_combo"]} for order in orders])
    member_frame = pd.DataFrame([{"customer_id": member["id"], "등급": grade_of(member, last.date(), **ar.DEFAULT_RULE)}
                                 for member in members])
    expected = summarize(frame, member_frame, tables=30)
    actual = sales_insights(orders, members, 30, last.date(), ar.DEFAULT_RULE)
    assert {key: actual[key] for key in expected} == expected


def test_api_dashboard_ignores_dummy_orders_and_refreshes(server, monkeypatch):
    from app import dummy

    # 주문 목록과 3번의 그래프가 모두 실제 DB 주문을 읽어야 한다.
    monkeypatch.setattr(dummy, "orders", lambda: [])
    now = datetime.now(timezone.utc)
    server.app.state.db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                            (7, 12345, now.isoformat()))
    repo = ar.AdminRepository(ar.ApiBackend("admin-secret"))
    assert len(repo.orders()) == 1 and repo.sales_insights()["revenue"] == 12345
    screen = open_dashboard(monkeypatch)
    html = "\n".join(element.value for element in screen.get("html"))
    assert '오늘 매출</div><div class="v">12,345' in html
    assert '최근 평균 객단가</div><div class="v">12,345' in html
    assert "시간대별 매출" in html and "주문 금액대 분포" in html and "7번" in html
    server.app.state.db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                            (7, 10000, now.isoformat()))
    screen.button(key="dashboard_refresh").click().run()
    assert not screen.exception
    html = "\n".join(element.value for element in screen.get("html"))
    assert '오늘 매출</div><div class="v">22,345' in html
    for tab in ("오늘 · 매출", "매출 추이", "고객 분석", "메뉴"):
        screen.sidebar.radio(key="nav_sub_대시보드").set_value(tab).run()
        assert not screen.exception


@pytest.mark.parametrize("days_ago", [1, 30])
def test_today_cards_do_not_reuse_old_db_sales(server, monkeypatch, days_ago):
    # 실제 DB 조회에서는 과거 매출을 오늘로 표시하지 않고 마지막 영업일 카드에만 유지한다.
    demo_day = datetime.now(timezone.utc) - timedelta(days=days_ago)
    for amount in (10000, 31000):
        server.app.state.db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                                (3, amount, demo_day.isoformat()))
    before = server.app.state.db.all("SELECT * FROM orders ORDER BY id")
    repo = ar.AdminRepository(ar.ApiBackend("admin-secret"))
    assert repo.stats()["today_orders"] == repo.sales_insights()["today_revenue"] == 0
    assert repo.sales_insights()["last_day_orders"] == 2
    screen = open_dashboard(monkeypatch)
    for tab in ("한눈에 보기", "오늘 · 매출"):
        screen.sidebar.radio(key="nav_sub_대시보드").set_value(tab).run()
        assert not screen.exception
        html = "\n".join(element.value for element in screen.get("html"))
        assert '오늘 주문</div><div class="v">0' in html
        assert '평균 주문금액</div><div class="v">-' in html
        assert '오늘 매출</div><div class="v">0' in html
        assert '마지막 영업일 매출</div><div class="v">41,000' in html
    assert server.app.state.db.all("SELECT * FROM orders ORDER BY id") == before


def test_dummy_mode_keeps_original_calculation():
    repo = ar.AdminRepository(ar.DummyBackend())
    assert repo.sales_insights() == summarize(repo.orders(), repo.members(), tables=repo.store()["tables"])
