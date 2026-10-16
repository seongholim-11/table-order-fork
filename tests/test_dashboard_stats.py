import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "admin"))

import admin_repository as ar  # noqa: E402
from admin_dummy_data import DummyBackend  # noqa: E402
from dashboard_stats import customer_care, menu_alerts, summarize  # noqa: E402


def test_summarize_dummy_data():
    repo = ar.AdminRepository(DummyBackend())
    x = summarize(repo.orders(), repo.members(), tables=30)
    assert not x["empty"]
    assert x["revenue"] == sum(x["by_hour"].values()) == sum(x["by_weekday"].values())
    assert x["avg_ticket"] == x["revenue"] // x["orders"]
    assert list(x["by_weekday"]) == ["월", "화", "수", "목", "금", "토", "일"]
    assert 0 <= x["returning_share"] <= 1


def test_summarize_empty():
    repo = ar.AdminRepository(DummyBackend())
    assert summarize(repo.orders().iloc[0:0], repo.members()) == {"empty": True}


def test_trend_stats():
    repo = ar.AdminRepository(DummyBackend())
    x = summarize(repo.orders(), repo.members(), tables=30)
    assert len(x["by_day"]) == 14
    assert sum(x["ticket_bands"].values()) == x["orders"]
    assert x["last_day_revenue"] == x["by_day"][x["last_day"]]
    assert 0 <= x["member_order_share"] <= 1
    assert x["member_revenue"] + x["guest_revenue"] == x["last_day_revenue"]
    assert 0 <= x["member_revenue_share"] <= 1
    tops = [c["amount"] for c in x["top_customers"]]
    assert tops == sorted(tops, reverse=True) and len(tops) <= 5
    assert all(c["table"] >= 1 and c["kind"] in ("회원", "비회원") for c in x["top_customers"])
    assert 0 < x["top_customer_share"] <= 1


def test_customer_care_and_menu_alerts():
    repo = ar.AdminRepository(DummyBackend())
    members = repo.members()
    care = customer_care(members)
    assert care["total"] == len(members)
    assert care["dormant"] == int((members["등급"] == "휴면").sum())
    assert customer_care(members.iloc[0:0]) == {"total": 0}
    alerts = menu_alerts(repo.menus(), [{"name": "노가리 구이"}, {"name": "계란말이"}])
    assert "노가리 구이" in alerts["sold_out"] and alerts["popular_sold_out"] == ["노가리 구이"]
