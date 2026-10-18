"""수용 3번: 실제 주문 집계·한국 날짜 경계·빈 데이터·인증을 검증한다."""

from datetime import timedelta

import pytest

from app.stores.stats import StatsStore
from tests.conftest import ADMIN
from tests.test_sooyong_today_orders import TODAY, add_order, today_client

PATHS = ("insights", "sales/hourly", "sales/weekday", "sales/trends", "sales/tickets", "tables")


def insert_order(client, at, amount, table=1, ai=False, member=None):
    """다른 담당자의 주문 쓰기 API 대신 테스트 DB에만 주문을 준비한다."""
    order_id = add_order(client, at, table_no=table, member_id=member)
    client.app.state.db.run("UPDATE orders SET total=?, ai_combo=? WHERE id=?", (amount, ai, order_id))
    return order_id


@pytest.mark.parametrize("path", PATHS)
def test_empty_and_auth_before_reading_database(today_client, monkeypatch, path):
    url = "/admin/api/stats/" + path
    assert today_client.get(url, headers=ADMIN).json() == {"empty": True}

    def unexpected_read(self):
        pytest.fail("인증 실패 전에 DB를 읽었습니다.")

    monkeypatch.setattr(StatsStore, "sales_orders", unexpected_read)
    assert today_client.get(url).status_code == 401


def test_known_totals_bands_turnover_and_subroutes(today_client):
    # 실제 오늘은 10/16이지만 마지막 주문일은 10/15이다. 오래된 매출을 오늘로 표시하면 안 된다.
    for at, amount, table, ai in [
        ("2026-10-15T15:00:00+09:00", 19999, 2, True),
        ("2026-10-15T17:00:00+09:00", 20000, 2, False),
        ("2026-10-15T18:00:00+09:00", 40000, 3, False),
        ("2026-10-14T19:00:00+09:00", 60000, 3, False),
        ("2026-10-08T19:00:00+09:00", 80000, 1, False),
        ("2026-09-16T00:00:00+09:00", 0, 1, False),
        ("2026-09-15T23:59:59.999999+09:00", 999999, 1, False),
    ]:
        insert_order(today_client, at, amount, table, ai)
    today_client.app.state.db.run("UPDATE store_info SET tables=?", (10,))
    data = today_client.get("/admin/api/stats/insights", headers=ADMIN).json()
    assert data["orders"] == 6 and data["days"] == 4
    assert data["revenue"] == 219999 and data["daily_revenue"] == 54999
    assert data["avg_ticket"] == 36666 and data["ai_avg_ticket"] == 19999
    assert data["plain_avg_ticket"] == 40000 and data["ai_share"] == 1 / 6
    assert data["ticket_bands"] == {"2만원 미만": 2, "2~4만원": 1, "4~6만원": 1, "6~8만원": 1, "8만원 이상": 1}
    assert data["today_revenue"] == 0 and data["last_order_date"] == "2026-10-15"
    assert data["last_day_revenue"] == 79999 and data["week_revenue"] == 139999
    assert data["week_change"] == (139999 - 80000) / 80000
    assert data["last_day_change"] == (79999 - 80000) / 80000
    assert len(data["by_day"]) == 14 and data["by_day"]["10/13"] == 0
    assert data["by_hour"]["16시"] == 0 and data["peak_hour"] == "19시"
    assert sum(data["by_hour"].values()) == sum(data["by_weekday"].values()) == data["revenue"]
    assert data["tables"] == 10 and data["turnover_today"] == 0.3 and data["turnover_avg"] == 0.1
    assert data["top_tables"] == {"2번": 2, "3번": 1}
    # 세부 API는 같은 집계에서 필요한 항목만 반환하며 별도 고정값을 쓰지 않는다.
    for path in PATHS[1:]:
        response = today_client.get("/admin/api/stats/" + path, headers=ADMIN)
        assert response.status_code == 200
        assert response.json() == {key: data[key] for key in response.json()}


@pytest.mark.parametrize("timestamp", ["2026-10-15 15:00:00", "2026-10-15T15:00:00Z",
                                        "2026-10-16T00:00:00+09:00"])
def test_kst_hour_day_and_zero_denominators(today_client, timestamp):
    insert_order(today_client, "2026-10-15T14:59:59.999999+00:00", 100)
    insert_order(today_client, timestamp, 0)
    data = today_client.get("/admin/api/stats/insights", headers=ADMIN).json()
    assert data["last_order_date"] == "2026-10-16" and data["today_revenue"] == 0
    assert data["by_hour"]["00시"] == 0 and data["by_hour"]["23시"] == 100
    assert data["by_weekday"]["목"] == 100 and data["by_weekday"]["금"] == 0
    assert data["last_day_change"] is data["week_change"] is data["ai_avg_ticket"] is None
    assert data["member_revenue_share"] is data["top_customer_share"] is None


def test_members_guests_preview_and_refresh(today_client):
    member = today_client.app.state.members.upsert_login("insights-member", "추가 통계 회원")
    today_client.app.state.db.run("UPDATE members SET visit_count=5 WHERE id=?", (member["id"],))
    insert_order(today_client, TODAY.isoformat(), 20000, 1, member=member["id"])
    insert_order(today_client, (TODAY + timedelta(hours=1)).isoformat(), 30000, 4, member=member["id"])
    insert_order(today_client, TODAY.isoformat(), 40000, 2)
    url = "/admin/api/stats/insights"
    data = today_client.get(url, headers=ADMIN).json()
    assert data["top_customers"][0] == {"name": "추가 통계 회원", "amount": 50000, "orders": 2, "table": 4, "kind": "회원"}
    assert data["member_revenue"] == 50000 and data["guest_revenue"] == 40000
    assert data["member_avg_ticket"] == 25000 and data["guest_avg_ticket"] == 40000
    assert data["returning_share"] == 1 and data["customer_grades"]["단골"] == 1
    preview = today_client.get(url + "?repeat=6&regular=10", headers=ADMIN).json()
    assert preview["customer_grades"]["신규"] == 1 and preview["returning_share"] == 0
    assert today_client.get(url, headers=ADMIN).json() == data
    insert_order(today_client, TODAY.isoformat(), 12345, 7)
    refreshed = today_client.get(url, headers=ADMIN).json()
    assert refreshed["orders"] == 4 and refreshed["today_revenue"] == 102345


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("query", ["repeat=1", "regular=2", "dormant=0", "repeat=5&regular=3", "regular=abc"])
def test_invalid_preview_is_rejected(today_client, path, query):
    assert today_client.get("/admin/api/stats/" + path + "?" + query, headers=ADMIN).status_code == 422
