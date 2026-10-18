"""수용: 고객 정보와 분리한 메뉴 품절 API의 DB 연동을 검증한다."""

import pytest

from app.stores.stats import StatsStore
from tests.conftest import ADMIN


@pytest.fixture(autouse=True)
def _empty_menus(client):
    """서버가 처음 뜰 때 기본 메뉴가 들어가므로, 빈 DB를 전제로 한 이 파일의 테스트를 위해 메뉴를 비운다."""
    client.app.state.db.run("DELETE FROM menus")


def add_menu(client, menu_id, name, soldout=False):
    """메뉴 쓰기 담당 영역을 바꾸지 않고 테스트 DB에만 메뉴를 준비한다."""
    client.app.state.db.run("INSERT INTO menus (id, category_id, name, price, is_soldout) VALUES (?, ?, ?, ?, ?)",
                             (menu_id, "anju", name, 1000, soldout))


def add_line(client, menu_id, name, qty=1, kind="menu"):
    """조합의 구성 수량과 일반 주문을 구분할 주문 줄을 만든다."""
    db = client.app.state.db
    order = db.run("INSERT INTO orders (table_no, total) VALUES (?, ?)", (1, 1000))
    return db.run("INSERT INTO order_items (order_id, menu_id, name, unit_price, qty, kind) VALUES (?, ?, ?, ?, ?, ?)",
                  (order, menu_id, name, 1000, qty, kind))


def get_alerts(client):
    response = client.get("/admin/api/alerts", headers=ADMIN)
    assert response.status_code == 200
    return response.json()


def test_empty_and_unauthenticated_requests(client, monkeypatch):
    assert get_alerts(client) == []

    def unexpected_read(self):
        pytest.fail("인증 없는 요청이 메뉴 DB를 읽었습니다.")

    monkeypatch.setattr(StatsStore, "menu_stock", unexpected_read)
    assert client.get("/admin/api/alerts").status_code == 401


def test_current_stock_and_restock_are_visible_without_orders(client):
    add_menu(client, "stock-a", "품절 예시", True)
    add_menu(client, "stock-b", "판매 중 예시")
    alerts = get_alerts(client)
    assert alerts == [{"kind": "soldout", "menu_id": "stock-a", "name": "품절 예시", "title": "품절 메뉴",
                       "detail": "품절 예시 메뉴가 현재 품절이에요.", "popular": False}]
    client.app.state.db.run("UPDATE menus SET is_soldout=? WHERE id=?", (False, "stock-a"))
    assert get_alerts(client) == []


def test_popularity_counts_components_times_combo_quantity_and_limits_top_ten(client):
    for index in range(12):
        menu_id = f"stock-{index:02}"
        add_menu(client, menu_id, f"메뉴{index:02}", index in (0, 11))
        add_line(client, menu_id, f"메뉴{index:02}", 20 - index)
    combo = add_line(client, None, "조합 이름은 메뉴가 아님", 3, "combo")
    client.app.state.db.run("INSERT INTO order_item_components (order_item_id, menu_id, name, qty) VALUES (?, ?, ?, ?)",
                             (combo, "stock-11", "메뉴11", 5))
    # 메뉴11은 9개 + (5개 × 3세트) = 24개로 TOP10에 진입한다.
    assert {row["menu_id"] for row in get_alerts(client) if row["popular"]} == {"stock-00", "stock-11"}
    client.app.state.db.run("DELETE FROM order_item_components WHERE order_item_id=?", (combo,))
    assert {row["menu_id"] for row in get_alerts(client) if row["popular"]} == {"stock-00"}


def test_menu_ids_survive_rename_and_ambiguous_legacy_names_are_not_guessed(client):
    add_menu(client, "renamed", "새 메뉴 이름", True)
    add_menu(client, "legacy", "ID 없는 옛 메뉴", True)
    add_menu(client, "duplicate-1", "동명 메뉴", True)
    add_menu(client, "duplicate-2", "동명 메뉴")
    add_line(client, "renamed", "주문할 당시의 이름", 2)
    add_line(client, None, "ID 없는 옛 메뉴", 3)
    add_line(client, None, "동명 메뉴", 100)
    rows = {row["menu_id"]: row for row in get_alerts(client)}
    assert rows["renamed"]["name"] == "새 메뉴 이름" and rows["renamed"]["popular"]
    assert rows["legacy"]["popular"] and not rows["duplicate-1"]["popular"]


def test_deleted_menu_id_does_not_fall_back_to_another_same_named_menu(client):
    add_menu(client, "remaining", "같은 이름", True)
    add_line(client, "deleted-id", "같은 이름", 10)
    assert not get_alerts(client)[0]["popular"]


def test_equal_quantities_have_repeatable_top_ten(client):
    for index in range(11):
        menu_id = f"tie-{index:02}"
        add_menu(client, menu_id, f"메뉴{index:02}", True)
        add_line(client, menu_id, f"메뉴{index:02}")
    rows = get_alerts(client)
    assert sum(row["popular"] for row in rows) == 10
    assert rows[-1]["menu_id"] == "tie-10" and not rows[-1]["popular"]
    assert get_alerts(client) == rows
