"""주문 이력 필터: 순수 함수 단위 테스트 + 화면(AppTest) 흐름."""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin")]

import pandas as pd
from streamlit.testing.v1 import AppTest

from order_filters import AI_NOT_USED, AI_USED, filter_orders

APP = str(ROOT / "admin" / "app.py")

DF = pd.DataFrame({
    "order_id": ["O0001", "O0002", "O0003", "O0004"],
    "주문 시각": pd.to_datetime(["2026-10-10 12:00", "2026-10-11 23:30", "2026-10-12 00:10", "2026-10-12 18:00"]),
    "customer_id": [1, 2, 1, 3], "닉네임": ["가", "나", "가", "비회원"], "테이블": [1, 2, 1, 3],
    "주문 내역": ["생맥주 500cc x2", "계란말이 x1, 어묵탕 x1", "Fried Chicken x1", "먹태구이 x1"],
    "금액": [10000, 25000, 18000, 40000], "AI 추천 사용": [False, True, False, True]})


def ids(df):
    return list(df["order_id"])


def test_no_conditions_returns_everything():
    assert ids(filter_orders(DF)) == ids(DF)


def test_period_is_inclusive_by_calendar_day():
    assert ids(filter_orders(DF, start=date(2026, 10, 11), end=date(2026, 10, 12))) == ["O0002", "O0003", "O0004"]
    assert ids(filter_orders(DF, start=date(2026, 10, 12), end=date(2026, 10, 12))) == ["O0003", "O0004"]
    assert ids(filter_orders(DF, end=date(2026, 10, 10))) == ["O0001"]


def test_tables_keyword_ai_and_amount_combine_with_and():
    assert ids(filter_orders(DF, tables=[1])) == ["O0001", "O0003"]
    assert ids(filter_orders(DF, keyword="어묵")) == ["O0002"]
    assert ids(filter_orders(DF, keyword="fried")) == ["O0003"]  # 대소문자 무시
    assert ids(filter_orders(DF, keyword="비회원")) == ["O0004"] and ids(filter_orders(DF, keyword="o0002")) == ["O0002"]
    assert ids(filter_orders(DF, ai=AI_USED)) == ["O0002", "O0004"] and ids(filter_orders(DF, ai=AI_NOT_USED)) == ["O0001", "O0003"]
    assert ids(filter_orders(DF, min_amount=18000, max_amount=30000)) == ["O0002", "O0003"]
    assert ids(filter_orders(DF, tables=[1], ai=AI_NOT_USED, min_amount=15000)) == ["O0003"]
    assert filter_orders(DF, keyword="없는메뉴").empty


def test_keyword_is_literal_not_regex():
    assert filter_orders(DF, keyword=".*").empty and filter_orders(DF, keyword="(").empty


# ---- 화면 ------------------------------------------------------------------------------------------------
def open_orders(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    app.sidebar.radio(key="nav_sub_주문 이력").set_value("전체 주문").run()
    assert not app.exception
    return app


def shown(app):
    return int(next(h.value.split('class="v">')[1].split("<")[0] for h in app.get("html") if "조회된 주문" in h.value))


def test_orders_page_filters_and_reset(monkeypatch):
    app = open_orders(monkeypatch)
    total = len(app.session_state["repo"].orders())
    assert shown(app) == total and app.button(key="of_reset").disabled
    app.multiselect(key="of_tables").set_value([12]).run()
    assert not app.exception and 0 < shown(app) < total and not app.button(key="of_reset").disabled
    app.selectbox(key="of_ai").set_value("AI 추천 사용").run()
    n_ai_table = shown(app)
    assert n_ai_table <= len(app.session_state["repo"].orders().query("테이블 == 12"))
    app.text_input(key="of_keyword").set_value("존재하지않는메뉴").run()
    assert any("조건에 맞는 주문이 없어요" in i.value for i in app.info)
    app.button(key="of_reset").click().run()
    assert not app.exception and shown(app) == total and app.button(key="of_reset").disabled


def test_period_presets_use_latest_order_day_as_reference(monkeypatch):
    app = open_orders(monkeypatch)
    orders = app.session_state["repo"].orders()
    last = orders["주문 시각"].max().date()
    app.selectbox(key="of_preset").set_value("오늘").run()
    assert shown(app) == int((orders["주문 시각"].dt.date == last).sum())
    app.selectbox(key="of_preset").set_value("직접 선택").run()
    assert not app.exception and app.date_input(key="of_period")
