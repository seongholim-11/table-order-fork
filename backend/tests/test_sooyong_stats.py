"""수용 2번: DB 기록부터 기본 통계 API까지 계산 규칙을 검증한다."""

from datetime import date

import pytest

from app.services.grades import AGE_GROUPS
from app.services.stats import dashboard
from tests.conftest import ADMIN
from tests.test_sooyong_today_orders import TODAY, add_order, today_client


def test_basic_stats_with_combo_members_and_yesterday(today_client):
    state = today_client.app.state
    new = state.members.upsert_login("new-stats", "신규", birth_year=2000, gender="male")
    regular = state.members.upsert_login("regular-stats", "단골", birth_year=1990, gender="female")
    dormant = state.members.upsert_login("dormant-stats", "휴면")
    state.db.run("UPDATE members SET visit_count=5, last_visit_at=? WHERE id=?", (TODAY.isoformat(), regular["id"]))
    state.db.run("UPDATE members SET visit_count=10, last_visit_at=? WHERE id=?",
                 ("2026-01-01T00:00:00+00:00", dormant["id"]))
    first = add_order(today_client, TODAY.isoformat(), member_id=new["id"])
    add_order(today_client, TODAY.isoformat(), member_id=new["id"])
    add_order(today_client, TODAY.isoformat(), member_id=regular["id"])
    add_order(today_client, TODAY.isoformat(), member_id=dormant["id"])
    add_order(today_client, TODAY.isoformat())
    yesterday = add_order(today_client, "2026-10-15T00:00:00+09:00", member_id=regular["id"])
    state.db.run("UPDATE orders SET total=100000 WHERE id=?", (yesterday,))
    state.db.run("UPDATE orders SET total=10001, ai_combo=? WHERE id=?", (True, first))
    line = state.db.run("INSERT INTO order_items (order_id, kind, name, unit_price, qty) VALUES (?, ?, ?, ?, ?)",
                        (first, "combo", "조합 이름은 순위에 제외", 5000, 2))
    state.db.run("INSERT INTO order_item_components (order_item_id, name, qty) VALUES (?, ?, ?)", (line, "통닭", 3))
    state.db.run("INSERT INTO order_items (order_id, name, unit_price, qty) VALUES (?, ?, ?, ?)",
                 (yesterday, "통닭", 1000, 1))
    for _ in range(4):
        state.db.run("INSERT INTO recommendation_events (table_no) VALUES (?)", (1,))
    response = today_client.get("/admin/api/stats", headers=ADMIN)
    assert response.status_code == 200
    stats = response.json()
    assert stats["today_orders"] == 5 and stats["avg_order_amount"] == 10000
    assert stats["new_customers"] == 1 and stats["returning_customers"] == 1
    assert stats["age_groups"]["20대"] == 1 and stats["age_groups"]["30대"] == 1
    assert stats["genders"] == {"남": 1, "여": 1}
    assert stats["popular_menus"] == [{"name": "통닭", "qty": 7}]
    assert stats["ai"]["recommendations"] == 4 and stats["ai"]["ai_orders"] == 1
    assert stats["ai"]["hit_rate"] == 0.25 and stats["ai"]["definition"]
    # 쿼리 미리보기는 기존 회원 방문 기록과 기본 설정을 변경하지 않는다.
    preview = today_client.get("/admin/api/stats?repeat=6&regular=10", headers=ADMIN).json()
    assert preview["new_customers"] == 2 and preview["returning_customers"] == 0
    assert today_client.get("/admin/api/stats", headers=ADMIN).json() == stats


@pytest.mark.parametrize(("suffix", "keys"), [
    ("sales", ("today_orders", "avg_order_amount")),
    ("menus/ranking", ("popular_menus",)),
    ("customers", ("new_customers", "returning_customers", "age_groups", "genders")),
    ("ai-recommendations", None),
])
def test_subroutes_match_dashboard_and_require_auth(today_client, suffix, keys):
    add_order(today_client, TODAY.isoformat())
    full = today_client.get("/admin/api/stats", headers=ADMIN).json()
    path = "/admin/api/stats/" + suffix
    response = today_client.get(path, headers=ADMIN)
    assert response.status_code == 200
    assert response.json() == ({key: full[key] for key in keys} if keys else full["ai"])
    assert today_client.get(path).status_code == 401
    assert today_client.get(path + "?repeat=5&regular=3", headers=ADMIN).status_code == 422


@pytest.mark.parametrize("query", ["repeat=1", "regular=2", "dormant=0", "regular=abc"])
def test_reject_invalid_rules(today_client, query):
    assert today_client.get("/admin/api/stats?" + query, headers=ADMIN).status_code == 422


def test_top_ten_and_empty_demographics():
    # 같은 수량일 때 이름순으로 고정해 새로고침마다 순위가 흔들리지 않게 한다.
    orders = [{"ts": "2026-10-16T00:00:00+09:00", "member_id": None, "total": 0, "ai_combo": True,
               "lines": [{"name": f"menu-{i:02}", "qty": 1} for i in range(12)]}]
    result = dashboard(orders, [], 0, date(2026, 10, 16), {})
    assert [menu["name"] for menu in result["popular_menus"]] == [f"menu-{i:02}" for i in range(10)]
    assert result["age_groups"] == dict.fromkeys(AGE_GROUPS, 0)
    assert result["genders"] == {} and result["ai"]["hit_rate"] is None
