"""관리자 로그인 직후 대시보드 첫 화면과 사이드바 순서 테스트."""

import sys
from datetime import timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]
APP = str(ROOT / "admin" / "app.py")

import admin_repository as repo_mod
from admin.admin_dummy_data import DUMMY_ORDER_COUNT, DUMMY_TODAY_ORDER_COUNT
from dashboard_stats import summarize


def open_dashboard(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("APP_ENV", "prod")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_dashboard_is_first_and_combines_today_with_sales_trend(monkeypatch):
    app = open_dashboard(monkeypatch)

    assert not app.exception
    assert app.query_params["page"] == "대시보드"
    assert app.query_params["tab"] == "한눈에 보기"
    assert app.sidebar.expander[0].label == "📊 대시보드"
    assert app.sidebar.radio(key="nav_sub_대시보드").options[0] == "한눈에 보기"

    html = "\n".join(element.value for element in app.get("html"))
    assert "오늘 주문" in html and "최근 7일 매출" in html and "일별 매출 (최근 14일)" in html
    assert html.index("일별 매출 (최근 14일)") < html.index("인기 메뉴 TOP 10")


def test_dummy_orders_include_members_and_guests(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    repo = repo_mod.connect("change-me").repo
    summary = summarize(repo.orders(), repo.members(repo_mod.DEFAULT_RULE))

    assert 0 < summary["member_order_share"] < 1
    assert summary["member_avg_ticket"] is not None
    assert summary["guest_avg_ticket"] is not None


def test_all_dashboard_sales_metrics_follow_dummy_orders(monkeypatch):
    """대시보드 숫자가 별도 고정값이 아니라 같은 주문·회원 데이터에서 계산되는지 확인한다."""
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    repo = repo_mod.connect("change-me").repo
    orders, members = repo.orders(), repo.members(repo_mod.DEFAULT_RULE)
    summary = summarize(orders, members, tables=repo.store()["tables"])
    recent = orders[orders["주문 시각"] >= orders["주문 시각"].max().normalize() - timedelta(days=29)]
    member_orders = recent[recent["customer_id"].notna()]
    guest_orders = recent[recent["customer_id"].isna()]

    assert len(orders) == DUMMY_ORDER_COUNT
    assert repo.stats(repo_mod.DEFAULT_RULE)["today_orders"] == DUMMY_TODAY_ORDER_COUNT
    assert summary["orders"] == len(recent)
    assert summary["revenue"] == int(recent["금액"].sum())
    assert summary["avg_ticket"] == summary["revenue"] // summary["orders"]
    assert summary["member_order_share"] == len(member_orders) / len(recent)
    assert summary["member_avg_ticket"] == int(member_orders["금액"].mean())
    assert summary["guest_avg_ticket"] == int(guest_orders["금액"].mean())
    assert summary["tables"] == 30
    assert summary["turnover_avg"] == round(len(recent) / summary["days"] / 30, 1)
    assert summary["last_day_revenue"] == summary["by_day"][summary["last_day"]]
    assert sum(summary["ticket_bands"].values()) == summary["orders"]

    buyer_ids = {int(value) for value in recent["customer_id"].dropna().unique()}
    buyer_grades = members[members["customer_id"].isin(buyer_ids)]["등급"]
    expected_returning = buyer_grades.isin(["재방문", "단골"]).sum() / len(buyer_grades)
    assert summary["returning_share"] == expected_returning

    # 인기 메뉴도 같은 1,000건 주문의 수량 합계로 계산되어야 한다.
    quantities = {}
    for order in repo.backend.orders_:
        for line in order["lines"]:
            quantities[line["name"]] = quantities.get(line["name"], 0) + line["qty"]
    expected_popular = sorted(quantities.items(), key=lambda item: -item[1])[:10]
    actual_popular = [(item["name"], item["qty"]) for item in repo.stats(repo_mod.DEFAULT_RULE)["popular_menus"]]
    assert actual_popular == expected_popular
