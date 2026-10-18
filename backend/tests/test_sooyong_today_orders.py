"""수용: 기본 통계에서도 오늘 주문의 날짜 경계와 새로고침을 검증한다."""

from datetime import datetime, timedelta

import pytest

from app.routers.admin import stats as stats_routes
from app.services.grades import KST
from app.stores.stats import StatsStore
from tests.conftest import ADMIN

TODAY = datetime(2026, 10, 16, 12, tzinfo=KST)


@pytest.fixture
def today_client(client, monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return TODAY.astimezone(tz) if tz else TODAY.replace(tzinfo=None)

    # 실행 날짜와 관계없이 같은 KST 하루 범위를 검증한다.
    monkeypatch.setattr(stats_routes, "datetime", FixedDatetime)
    return client


def add_order(client, created_at, table_no=1, member_id=None):
    """주문 저장 기능은 다른 담당자 작업이므로 테스트 DB에만 주문을 직접 준비한다."""
    return client.app.state.db.run(
        "INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
        (table_no, member_id, 10000, created_at))


def test_empty_database_returns_zero_stats(today_client):
    response = today_client.get("/admin/api/stats", headers=ADMIN)
    assert response.status_code == 200
    data = response.json()
    assert data["today_orders"] == data["avg_order_amount"] == 0
    assert data["popular_menus"] == []
    assert data["ai"]["recommendations"] == 0 and data["ai"]["hit_rate"] is None


@pytest.mark.parametrize(("created_at", "expected"), [
    ("2026-10-15T14:59:59.999999+00:00", 0),
    ("2026-10-15T15:00:00+00:00", 1),
    ("2026-10-16T14:59:59.999999+00:00", 1),
    ("2026-10-16T15:00:00+00:00", 0),
    ("2026-10-16T00:00:00+09:00", 1),
    ("2026-10-16T23:59:59.999999+09:00", 1),
    ("2026-10-17T00:00:00+09:00", 0),
    ("2026-10-15 15:00:00", 1),
    ("2026-10-15 14:59:59", 0),
    ("2026-10-16T14:59:59", 1),
    ("2026-10-16T00:00:00Z", 1),
])
def test_today_uses_kst_boundaries_and_handles_timestamp_formats(today_client, created_at, expected):
    add_order(today_client, created_at)
    assert today_client.get("/admin/api/stats", headers=ADMIN).json()["today_orders"] == expected


def test_counts_orders_not_members_tables_or_menu_quantities(today_client):
    member = today_client.app.state.members.upsert_login("order-count", "주문 건수 확인")
    now = TODAY.isoformat()
    first = add_order(today_client, now, table_no=1, member_id=member["id"])
    add_order(today_client, now, table_no=1, member_id=member["id"])
    add_order(today_client, now, table_no=2)  # 비회원 주문도 한 건이다.
    for name, qty in (("메뉴A", 10), ("메뉴B", 20)):
        today_client.app.state.db.run(
            "INSERT INTO order_items (order_id, name, unit_price, qty) VALUES (?, ?, ?, ?)",
            (first, name, 100, qty))
    assert today_client.get("/admin/api/stats", headers=ADMIN).json()["today_orders"] == 3


def test_database_changes_are_visible_on_next_request(today_client):
    assert today_client.get("/admin/api/stats", headers=ADMIN).json()["today_orders"] == 0
    add_order(today_client, TODAY.isoformat())
    assert today_client.get("/admin/api/stats", headers=ADMIN).json()["today_orders"] == 1
    assert StatsStore(today_client.app.state.db).count_orders_on(TODAY.date() + timedelta(days=1)) == 0


def test_stats_require_admin_before_querying_orders(client, monkeypatch):
    def unexpected_query(self):
        pytest.fail("인증 없는 요청에서 주문을 조회했습니다.")

    monkeypatch.setattr(StatsStore, "orders", unexpected_query)
    assert client.get("/admin/api/stats").status_code == 401
