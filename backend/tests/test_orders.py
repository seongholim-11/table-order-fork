"""주문 저장·테이블 누적·관리자 주문 이력의 실제 DB 동작을 확인한다."""

from tests.conftest import ADMIN, login


def line(menu_id="c1", name="통닭", unit=18000, qty=1):
    return {"id": menu_id, "name": name, "unit": unit, "qty": qty}


def test_create_order_saves_guest_member_and_combo_rows(client):
    for menu_id, name in (("test-c1", "통닭"), ("test-b1", "생맥주")):
        client.app.state.db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
                                (menu_id, "test", name, 1000))
    guest = client.post("/api/v1/orders", json={"table_no": 3, "lines": [line(menu_id="test-c1")], "total": 18000})
    assert guest.status_code == 201

    member_headers = login(client, "주문회원")
    combo = {"id": "combo:classic", "name": "AI 조합", "unit": 30000, "qty": 1,
             "components": [{"id": "test-c1", "name": "통닭", "qty": 1}, {"id": "test-b1", "name": "생맥주", "qty": 2}]}
    saved = client.post("/api/orders", headers=member_headers,
                        json={"table_no": 3, "lines": [combo], "total": 30000, "coupon_ids": [7]})
    assert saved.status_code == 201 and saved.json()["ai_combo"] is True
    assert saved.json()["used_coupon_ids"] == []

    rows = client.app.state.shop.orders()
    assert [row["member_id"] for row in rows] == [client.get("/api/members/me", headers=member_headers).json()["id"], None]
    combo_row = rows[0]
    assert combo_row["ai_combo"] is True and combo_row["lines"][0]["id"].startswith("combo:")
    components = client.app.state.db.all("SELECT * FROM order_item_components WHERE order_item_id=?",
                                         (client.app.state.db.one("SELECT id FROM order_items WHERE kind='combo'")["id"],))
    assert len(components) == 2 and {row["menu_id"] for row in components} == {"test-c1", "test-b1"}


def test_order_lines_are_required(client):
    assert client.post("/api/orders", json={"table_no": 1, "lines": [], "total": 0}).status_code == 422


def test_table_orders_start_at_first_valid_login_and_filter_table(client):
    headers = login(client, "테이블손님")
    member_id = client.get("/api/members/me", headers=headers).json()["id"]
    client.post("/api/orders", json={"table_no": 7, "lines": [line()], "total": 18000})
    client.app.state.db.run("UPDATE orders SET created_at=? WHERE table_no=?", ("2000-01-01T00:00:00+00:00", 7))
    client.app.state.tablet_logins.record(7, member_id, "테이블손님")
    client.post("/api/orders", json={"table_no": 7, "lines": [line(qty=2)], "total": 36000})
    client.post("/api/orders", json={"table_no": 8, "lines": [line()], "total": 18000})

    result = client.get("/api/v1/tables/7/orders")
    assert result.status_code == 200
    assert len(result.json()["orders"]) == 1 and result.json()["total"] == 36000
    assert client.get("/api/v1/tables/99/orders").json() == {"orders": [], "total": 0}


def test_admin_orders_are_real_latest_first_and_filterable(client):
    headers = login(client, "관리자주문회원")
    member_id = client.get("/api/members/me", headers=headers).json()["id"]
    client.post("/api/orders", headers=headers, json={"table_no": 2, "lines": [line()], "total": 18000})
    client.post("/api/orders", json={"table_no": 4, "lines": [line(qty=2)], "total": 36000})
    result = client.get("/admin/api/orders", headers=ADMIN)
    assert result.status_code == 200 and [row["table_no"] for row in result.json()] == [4, 2]
    assert result.json()[1]["nickname"] == "관리자주문회원" and result.json()[0]["nickname"] is None
    mine = client.get("/admin/api/orders", headers=ADMIN, params={"member_id": member_id})
    assert len(mine.json()) == 1 and mine.json()[0]["member_id"] == member_id
    assert client.get("/admin/api/orders").status_code == 401
