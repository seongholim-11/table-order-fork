"""시연 주문의 합계·반복 실행·실패 시 전체 취소를 검증한다."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.stores.sales_demo import (DEMO_LABEL, LEGACY_LABEL, consolidate_sales_demo_orders,
                                   rebalance_sales_demo_tables, sales_demo_menus, seed_sales_demo)
from tests.conftest import ADMIN


@pytest.fixture(autouse=True)
def _empty_menus(client):
    """서버가 처음 뜰 때 기본 메뉴가 들어가므로, 빈 DB를 전제로 한 이 파일의 테스트를 위해 메뉴를 비운다."""
    client.app.state.db.run("DELETE FROM menus")


TODAY = date(2026, 10, 17)


def prepare_menu(db):
    """안주·주류·음료에 주문을 나눌 수 있도록 실제 단가를 가진 메뉴들을 준비한다."""
    for menu_id, category, price in (("fish", "anju", 14000), ("egg", "anju", 16000),
                                      ("soup", "soup", 12000), ("beer", "beer", 5000),
                                      ("soju", "soju", 5000), ("cola", "drink", 3000)):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
               (menu_id, category, menu_id, price))


def test_preview_apply_and_repeat_match_actual_api(client):
    db = client.app.state.db
    prepare_menu(db)
    for stamp, total in (("2026-10-17T10:00:00+09:00", 40000),
                         ("2026-10-10T10:00:00+09:00", 80000),
                         ("2026-10-09T10:00:00+09:00", 100000)):
        db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (1, total, stamp))
    originals = db.all("SELECT * FROM orders ORDER BY id")
    preview = seed_sales_demo(db, TODAY)
    assert preview["created_order_ids"] == [] and preview["planned_orders"] > 0
    assert db.all("SELECT * FROM orders ORDER BY id") == originals

    result = seed_sales_demo(db, TODAY, apply=True)
    assert result["after"] == preview["after"]
    actual = client.get("/admin/api/stats/insights", headers=ADMIN).json()
    for key in ("last_order_date", "last_day_revenue", "week_revenue", "last_day_change", "week_change"):
        assert actual[key] == result["after"][key]
    assert .03 <= actual["last_day_change"] <= .18
    assert -.15 <= actual["week_change"] <= -.01
    # 기존 주문을 유지하면서 추가 주문만큼만 매출이 늘고, 메뉴 줄의 합계도 맞는지 확인한다.
    assert db.all("SELECT * FROM orders WHERE id<=? ORDER BY id", (originals[-1]["id"],)) == originals
    lines = db.all("SELECT o.total, i.qty, i.unit_price, i.option_label, i.menu_id FROM orders o "
                   "JOIN order_items i ON i.order_id=o.id")
    assert len(lines) >= result["planned_orders"]
    assert all(1 <= line["qty"] <= 3 and line["option_label"] == DEMO_LABEL for line in lines)
    assert len({line["menu_id"] for line in lines}) >= 5
    assert not db.all("SELECT o.id FROM orders o JOIN order_items i ON i.order_id=o.id "
                      "GROUP BY o.id, o.total HAVING SUM(i.qty*i.unit_price)<>o.total")
    repeated = seed_sales_demo(db, TODAY, apply=True)
    assert repeated["created_order_ids"] == [] and repeated["added_amount"] == 0
    assert repeated["after"] == result["after"]


@pytest.mark.parametrize("has_latest_order", [False, True])
def test_missing_comparison_day_stops_without_inventing_reference_orders(client, has_latest_order):
    db = client.app.state.db
    prepare_menu(db)
    if has_latest_order:
        db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
               (1, 10000, "2026-10-17T00:30:00+09:00"))
    # 비교 자료가 없을 때 수치를 임의로 크게 만들지 않고, 아무것도 쓰지 않은 채 중단한다.
    before = db.all("SELECT * FROM orders ORDER BY id")
    with pytest.raises(ValueError, match="기존 매출"):
        seed_sales_demo(db, TODAY, apply=True)
    assert db.all("SELECT * FROM orders ORDER BY id") == before
    assert db.all("SELECT * FROM order_items") == []


def test_item_failure_rolls_back_all_demo_orders(client, monkeypatch):
    db = client.app.state.db
    prepare_menu(db)
    for stamp, total in (("2026-10-10T18:00:00+09:00", 80000), ("2026-10-09T18:00:00+09:00", 100000)):
        db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (1, total, stamp))
    legacy = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                    (1, 42000, "2026-10-17T12:00:00+09:00"))
    db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, option_label) VALUES (?, ?, ?, ?, ?, ?)",
           (legacy, "fish", "fish", 3, 14000, LEGACY_LABEL))
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    execute = db._execute

    def reject_item(sql, params=()):
        # 주문만 남고 메뉴 내역이 빠지는 상황을 만들기 위해 메뉴 줄 저장을 실패시킨다.
        if sql.startswith("INSERT INTO order_items"):
            raise RuntimeError("메뉴 내역 저장 실패 재현")
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", reject_item)
    with pytest.raises(RuntimeError):
        seed_sales_demo(db, TODAY, apply=True)
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines


def test_postgres_datetime_values_use_the_same_kst_day(client, monkeypatch):
    db = client.app.state.db
    prepare_menu(db)
    execute = db._execute

    def postgres_timestamps(sql, params=()):
        # PostgreSQL 드라이버가 돌려주는 UTC datetime을 그대로 재현한다.
        if sql == "SELECT id, total, created_at FROM orders":
            return SimpleNamespace(fetchall=lambda: [
                {"id": 1, "total": 40000, "created_at": datetime.fromisoformat("2026-10-16T15:30:00+00:00")},
                {"id": 2, "total": 80000, "created_at": datetime.fromisoformat("2026-10-09T15:30:00+00:00")},
            ])
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", postgres_timestamps)
    result = seed_sales_demo(db, TODAY)
    assert result["before"]["last_order_date"] == "2026-10-17"
    assert result["before"]["last_day_revenue"] == 40000
    assert result["before"]["previous_day_revenue"] == 80000
    assert .03 <= result["after"]["last_day_change"] <= .18
    assert result["after"]["week_change"] < 0


def test_legacy_replacement_distributes_menus_and_keeps_weights(client):
    db = client.app.state.db
    prepare_menu(db)
    for stamp, total in (("2026-10-10T18:00:00+09:00", 500000), ("2026-10-09T18:00:00+09:00", 600000)):
        db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (1, total, stamp))
    original = db.all("SELECT * FROM orders ORDER BY id")
    legacy = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                    (1, 42000, "2026-10-17T12:00:00+09:00"))
    db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, option_label) VALUES (?, ?, ?, ?, ?, ?)",
           (legacy, "fish", "fish", 3, 14000, LEGACY_LABEL))
    weights = {row["id"]: row["weight"] for row in sales_demo_menus(db)}
    result = seed_sales_demo(db, TODAY, apply=True)
    assert result["replaced_order_ids"] == [legacy]
    assert db.one("SELECT id FROM orders WHERE id=?", (legacy,)) is None
    assert db.all("SELECT * FROM orders WHERE id<=? ORDER BY id", (original[-1]["id"],)) == original
    distribution = sales_demo_menus(db)
    assert {row["id"]: row["weight"] for row in distribution} == weights
    assert all(row["demo_qty"] > 0 for row in distribution)
    assert max(row["demo_qty"] for row in distribution) / sum(row["demo_qty"] for row in distribution) < .30
    before_repeat = db.all("SELECT * FROM orders ORDER BY id")
    assert seed_sales_demo(db, TODAY, apply=True)["unchanged"]
    assert db.all("SELECT * FROM orders ORDER BY id") == before_repeat


def test_changed_demo_is_not_deleted(client):
    db = client.app.state.db
    prepare_menu(db)
    order = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                   (1, 14000, "2026-10-17T12:00:00+09:00"))
    db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, option_label) VALUES (?, ?, ?, ?, ?, ?)",
           (order, "fish", "fish", 2, 14000, LEGACY_LABEL))
    before = db.all("SELECT * FROM orders")
    with pytest.raises(ValueError, match="다른 내역"):
        seed_sales_demo(db, TODAY, apply=True)
    assert db.all("SELECT * FROM orders") == before


def prepare_table_orders(client):
    """매출과 메뉴 수량을 바꾸지 않고 나눌 수 있는 기존 시연 주문 20건을 만든다."""
    db = client.app.state.db
    prepare_menu(db)
    db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
           (4, 100000, "2026-10-10T18:00:00+09:00"))
    for index in range(20):
        stamp = f"2026-10-17T{17 + index % 3:02d}:00:00+09:00"
        order = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)", (index + 1, 22000, stamp))
        for menu_id, price in (("fish", 14000), ("beer", 5000), ("cola", 3000)):
            db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, option_label) VALUES (?, ?, ?, ?, ?, ?)",
                   (order, menu_id, menu_id, 1, price, DEMO_LABEL))


def test_table_rebalance_keeps_revenue_menu_quantities_and_other_days(client):
    prepare_table_orders(client)
    db = client.app.state.db
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_menus = sales_demo_menus(db)
    before_store = db.all("SELECT * FROM store_info")
    before_api = client.get("/admin/api/stats/insights", headers=ADMIN).json()
    preview = rebalance_sales_demo_tables(db)
    assert preview["before_orders"] == 20 and preview["after_orders"] == 30
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    result = rebalance_sales_demo_tables(db, apply=True)
    actual = client.get("/admin/api/stats/insights", headers=ADMIN).json()
    assert actual["top_tables"] == {"7번": 6, "12번": 5, "3번": 4, "9번": 3, "14번": 2}
    assert len(result["table_counts"]) == 15 and len(set(result["order_amounts"])) >= 3
    for key in ("revenue", "last_day_revenue", "week_revenue", "last_day_change", "week_change",
                "by_hour", "by_weekday", "by_day"):
        assert actual[key] == before_api[key]
    assert sales_demo_menus(db) == before_menus and db.all("SELECT * FROM store_info") == before_store
    assert db.one("SELECT * FROM orders WHERE id=?", (before_orders[0]["id"],)) == before_orders[0]
    assert not db.all("SELECT o.id FROM orders o JOIN order_items i ON i.order_id=o.id "
                      "GROUP BY o.id, o.total HAVING SUM(i.qty*i.unit_price)<>o.total")
    after_orders = db.all("SELECT * FROM orders ORDER BY id")
    repeated = rebalance_sales_demo_tables(db, apply=True)
    assert repeated["unchanged"] and repeated["created_order_ids"] == []
    assert db.all("SELECT * FROM orders ORDER BY id") == after_orders


def test_table_rebalance_failure_restores_orders_and_items(client, monkeypatch):
    prepare_table_orders(client)
    db = client.app.state.db
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    execute = db._execute

    def fail_item(sql, params=()):
        # 이전 시연을 지운 뒤 새 메뉴 줄 저장이 실패해도 원래 주문까지 복원돼야 한다.
        if sql.startswith("INSERT INTO order_items"):
            raise RuntimeError("메뉴 내역 저장 실패 재현")
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", fail_item)
    with pytest.raises(RuntimeError):
        rebalance_sales_demo_tables(db, apply=True)
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines


def prepare_consolidation(client):
    """실제 단가로 총 615,000원인 시연 주문을 기존 30건 형태로 준비한다."""
    prepare_table_orders(client)
    db = client.app.state.db
    for _ in range(5):
        order = db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?, ?, ?)",
                       (7, 35000, "2026-10-17T17:30:00+09:00"))
        for menu_id, price in (("fish", 14000), ("egg", 16000), ("beer", 5000)):
            db.run("INSERT INTO order_items (order_id, menu_id, name, unit_price, qty, option_label) "
                   "VALUES (?, ?, ?, ?, ?, ?)", (order, menu_id, menu_id, price, 1, DEMO_LABEL))
    rebalance_sales_demo_tables(db, apply=True)


def test_consolidation_keeps_real_menu_prices_quantities_table_revenue_and_other_data(client):
    prepare_consolidation(client)
    db = client.app.state.db
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    before_menus = sales_demo_menus(db)
    before_members = client.app.state.members.all()
    preview = consolidate_sales_demo_orders(db)
    assert preview["before_orders"] == 30 and preview["after_orders"] == 15
    assert preview["total"] == 615000 and preview["average"] == 41000
    assert len(set(preview["table_amounts"].values())) >= 3
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines

    result = consolidate_sales_demo_orders(db, apply=True)
    actual = client.get("/admin/api/stats/insights", headers=ADMIN).json()
    assert result["table_amounts"] == preview["table_amounts"]
    assert len(result["removed_order_ids"]) == 15
    assert actual["last_day_orders"] == 15 and actual["last_day_revenue"] == 615000
    assert actual["last_day_revenue"] // actual["last_day_orders"] == 41000
    assert sales_demo_menus(db) == before_menus and client.app.state.members.all() == before_members
    assert db.one("SELECT * FROM orders WHERE id=?", (before_orders[0]["id"],)) == before_orders[0]
    # 주문 연결만 바꾸고 기존 메뉴 줄의 ID·이름·단가·수량은 모두 유지한다.
    assert [{key: value for key, value in line.items() if key != "order_id"}
            for line in db.all("SELECT * FROM order_items ORDER BY id")] == [
                {key: value for key, value in line.items() if key != "order_id"} for line in before_lines]
    assert not db.all("SELECT o.id FROM orders o JOIN order_items i ON i.order_id=o.id "
                      "GROUP BY o.id, o.total HAVING SUM(i.qty*i.unit_price)<>o.total")
    after_orders = db.all("SELECT * FROM orders ORDER BY id")
    repeated = consolidate_sales_demo_orders(db, apply=True)
    assert repeated["unchanged"] and repeated["removed_order_ids"] == []
    assert db.all("SELECT * FROM orders ORDER BY id") == after_orders


def test_consolidation_failure_restores_moved_lines_and_removed_orders(client, monkeypatch):
    prepare_consolidation(client)
    db = client.app.state.db
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    execute = db._execute

    def fail_delete(sql, params=()):
        # 메뉴 줄을 옮긴 뒤 삭제가 실패해도 전체 변경이 취소되어야 한다.
        if sql.startswith("DELETE FROM orders"):
            raise RuntimeError("주문 삭제 실패 재현")
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", fail_delete)
    with pytest.raises(RuntimeError):
        consolidate_sales_demo_orders(db, apply=True)
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines


def test_consolidation_rejects_prices_different_from_registered_menu(client):
    prepare_consolidation(client)
    db = client.app.state.db
    line = db.one("SELECT * FROM order_items WHERE option_label=? ORDER BY id LIMIT 1", (DEMO_LABEL,))
    db.run("UPDATE order_items SET unit_price=unit_price+100 WHERE id=?", (line["id"],))
    db.run("UPDATE orders SET total=total+? WHERE id=?", (100 * line["qty"], line["order_id"]))
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    with pytest.raises(ValueError, match="등록 메뉴 가격"):
        consolidate_sales_demo_orders(db, apply=True)
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines
