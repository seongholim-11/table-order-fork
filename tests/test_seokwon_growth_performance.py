"""석원 TODO 3: F&B그로스 성과 화면과 계산 기준 테스트."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import admin_repository as ar
from admin.views.growth_performance import growth_summary

APP = str(ROOT / "admin" / "app.py")


def open_growth(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["page"], app.query_params["tab"] = "마케팅", "F&B그로스 성과"
    app.run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_growth_summary_uses_one_month_basis_for_every_revenue_metric():
    repo = ar.connect("change-me").repo
    result = growth_summary(repo.orders(), repo.members())
    assert not result["empty"] and result["ai_orders"] > 0
    assert result["observed_ai_revenue"] <= result["observed_post_revenue"]
    assert result["ai_monthly_revenue"] == round(
        result["observed_ai_revenue"] / result["post_days"] * 30)
    assert result["monthly_growth"] == result["performance_monthly"] - result["baseline_monthly"]


def test_monthly_growth_uses_first_ai_order_as_adoption_date():
    start = datetime(2026, 10, 1)
    orders = pd.DataFrame([
        {"주문 시각": start + timedelta(days=day), "금액": amount, "AI 추천 사용": ai,
         "customer_id": None}
        for day, amount, ai in ((0, 100, False), (1, 100, False), (2, 200, True), (3, 200, True))
    ])
    members = pd.DataFrame(columns=["customer_id", "등급", "방문 횟수"])
    result = growth_summary(orders, members)
    assert result["adoption_date"] == "2026-10-03"
    assert result["baseline_monthly"] == 3_000
    assert result["performance_monthly"] == 6_000
    assert result["monthly_growth"] == 3_000 and result["growth_rate"] == 1


def test_growth_page_shows_only_growth_results_without_dashboard_duplicates(monkeypatch):
    app = open_growth(monkeypatch)
    assert not app.exception
    html = "\n".join(element.value for element in app.get("html"))
    assert "F&amp;B그로스 성과" in html
    assert "F&amp;B그로스와 함께한 결과" in html
    assert "1. 매출데이터" not in html and "2. 고객데이터" not in html
    for label in ("AI 추천 사용 주문", "AI 연동 월환산 매출", "최종 월환산 매출 차이",
                  "2회 이상 방문한 신규고객", "새로 방문한 휴면고객"):
        assert label in html
    assert not app.dataframe
    assert app.number_input[0].label == "성과 수수료율(%)"
    assert len(app.get("vega_lite_chart")) >= 2
    assert app.sidebar.radio(key="nav_sub_마케팅").value == "F&B그로스 성과"

