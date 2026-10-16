"""석원 담당 AI 마케팅 추천 초안의 성격별 모듈 테스트."""

import pandas as pd

from admin.marketing.config import EMPTY_RECOMMENDATION
from admin.marketing.consumer_data import summarize_consumers
from admin.marketing.menu_data import summarize_menus
from admin.marketing.recommendations import pick_recommendations, recommend
from admin.marketing.revenue_data import summarize_revenue


def test_consumer_revenue_and_menu_data_are_summarized_separately():
    members = pd.DataFrame([
        {"등급": "휴면", "마케팅 수신 동의": True, "수신거부": False},
        {"등급": "단골", "마케팅 수신 동의": True, "수신거부": True},
    ])
    orders = pd.DataFrame([{
        "주문 내역": "할맥 x2, 감자튀김 x1", "주문 시각": pd.Timestamp("2026-10-16 19:00"), "금액": 21000,
    }])
    menus = pd.DataFrame([
        {"메뉴명": "할맥", "판매 여부": True, "추천 가중치": 100},
        {"메뉴명": "떡볶이", "판매 여부": True, "추천 가중치": 50},
        {"메뉴명": "감자튀김", "판매 여부": False, "추천 가중치": 20},
    ])

    consumer_summary = summarize_consumers(members)
    revenue_summary, quantities = summarize_revenue(orders)
    menu_summary = summarize_menus(menus, quantities)

    assert consumer_summary["sendable"] == 1 and consumer_summary["opted_out"] == 1
    assert revenue_summary["revenue"] == 21000 and revenue_summary["top_items"][0] == ("할맥", 2)
    assert menu_summary["unsold"] == ["떡볶이"] and menu_summary["soldout"] == ["감자튀김"]


def test_empty_context_has_one_safe_recommendation():
    context = {
        "members": {"total": 0, "grades": {}, "sendable": 0, "opted_out": 0, "pool_by_grade": {}},
        "orders": {"count": 0, "revenue": 0, "avg": 0, "peak_hours": [], "busy_weekday": None, "top_items": []},
        "menus": {"total": 0, "on_sale": 0, "soldout": [], "high_weight": [], "unsold": []},
        "stats": {},
        "sms": {"logs": 0, "usage": None},
    }
    assert recommend(context) == [EMPTY_RECOMMENDATION]


def test_recommendation_pages_wrap_to_the_first_page():
    cards = [{"title": str(number)} for number in range(7)]
    first, first_page, pages = pick_recommendations(cards, 0)
    second, second_page, _ = pick_recommendations(cards, 1)

    assert (first_page, second_page, pages) == (1, 2, 2)
    assert [card["title"] for card in first] == ["0", "1", "2", "3"]
    assert [card["title"] for card in second] == ["4", "5", "6", "0"]
    assert pick_recommendations(cards, 2)[0] == first
