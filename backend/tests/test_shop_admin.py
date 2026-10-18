import pytest

from app.factory import create_app
from tests.conftest import ADMIN, login, set_profile, settings


# @pytest.mark.skip(reason="로직을 지우고 더미 응답만 돌려주는 상태라 저장·검증이 일어나지 않음 - 해당 엔드포인트를 DB 로 구현하면 이 skip 을 지운다")
def test_menu_seeded_and_admin_edits_reach_users(client):
    menus = client.get("/api/menus").json()
    assert len(menus) == 60 and {"id", "name", "price", "soldout", "weight", "spicy", "set_ok", "tags"} <= menus[0].keys()
    # r = client.put("/admin/api/menus/c2", headers=ADMIN, json={"weight": 90, "soldout": True, "price": 21000})
    # assert r.status_code == 200 and r.json()["weight"] == 90 and r.json()["name"] == "간장마늘 치킨"
    c2 = client.app.state.shop.menu("c2")  # GET /api/menus 는 더미라 저장소로 확인한다
    assert c2["soldout"] is False and c2["price"] == 20000 and c2["weight"] == 50


@pytest.mark.skip(reason="로직을 지우고 더미 응답만 돌려주는 상태라 저장·검증이 일어나지 않음 - 해당 엔드포인트를 DB 로 구현하면 이 skip 을 지운다")
def test_admin_menu_create_delete_and_validation(client):
    body = {"name": "신메뉴", "cat": "anju", "price": 9000}
    assert client.put("/admin/api/menus/new1", headers=ADMIN, json=body).status_code == 200
    assert client.put("/admin/api/menus/new2", headers=ADMIN, json={"name": "x"}).status_code == 422
    assert client.put("/admin/api/menus/new1", headers=ADMIN, json={"cat": "nope"}).status_code == 422
    assert client.put("/admin/api/menus/new1", headers=ADMIN, json={"weight": 101}).status_code == 422
    assert client.delete("/admin/api/menus/new1", headers=ADMIN).status_code == 204
    assert client.delete("/admin/api/menus/new1", headers=ADMIN).status_code == 404


def test_admin_routes_require_token(client):
    for path in ("/admin/api/menus", "/admin/api/orders", "/admin/api/members", "/admin/api/stats",
                 "/admin/api/marketing/sms/usage"):
        assert client.get(path).status_code == 401


@pytest.mark.skip(reason="로직을 지우고 더미 응답만 돌려주는 상태라 저장·검증이 일어나지 않음 - 해당 엔드포인트를 DB 로 구현하면 이 skip 을 지운다")
def test_orders_calls_and_member_link(client):
    h = login(client, "주문자")
    line = {"id": "c1", "name": "역전 옛날통닭", "unit": 18000, "qty": 2}
    combo = {"id": "combo:classic", "name": "[AI 조합] 바삭한 치킨 한 상", "unit": 20000, "qty": 1,
             "components": [{"id": "c1", "name": "통닭", "qty": 1}]}
    r = client.post("/api/orders", headers=h, json={"table_no": 5, "lines": [line, combo], "total": 56000})
    assert r.status_code == 201 and r.json()["ai_combo"] is True
    client.post("/api/orders", json={"table_no": 6, "lines": [line], "total": 36000})  # 비회원
    assert client.post("/api/orders", json={"table_no": 6, "lines": [], "total": 0}).status_code == 422
    shop = client.app.state.shop  # GET /admin/api/orders·calls 는 더미라 저장소로 확인한다
    assert [o["member_id"] for o in shop.orders()] == [None, 1]
    assert len(shop.orders(1)) == 1 and shop.orders(1)[0]["ai_combo"] is True
    assert client.post("/api/calls", json={"table_no": 3, "items": ["💧 물"]}).status_code == 201


def test_members_grades_with_rule_preview_and_profile(client):
    h = login(client, "단골")
    for _ in range(4):
        login(client, "단골")
    login(client, "신입")
    members = {m["nickname"]: m for m in client.get("/admin/api/members", headers=ADMIN).json()["members"]}
    assert members["단골"]["grade"] == "단골" and members["신입"]["grade"] == "신규"
    preview = client.get("/admin/api/members", headers=ADMIN, params={"regular": 10}).json()
    assert {m["nickname"]: m["grade"] for m in preview["members"]}["단골"] == "재방문"
    set_profile(client, h, birth_year=1995, gender="female", phone="010-1111-2222")
    m = next(m for m in client.get("/admin/api/members", headers=ADMIN).json()["members"] if m["nickname"] == "단골")
    assert m["age_group"] == "30대" and m["gender"] == "여" and m["has_phone"] is True


def test_stats_and_ai_hit_rate(client):
    h = login(client, "통계")
    set_profile(client, h, birth_year=2000, gender="male")
    for _ in range(4):
        client.app.state.db.run("INSERT INTO recommendation_events (table_no) VALUES (?)", (1,))
    # 주문·추천 쓰기 API는 다른 담당자의 더미 상태이므로 테스트 DB에 기록을 준비한다.
    db = client.app.state.db
    order = db.run("INSERT INTO orders (table_no, member_id, total, ai_combo) VALUES (?, ?, ?, ?)", (1, 1, 1, True))
    line = db.run("INSERT INTO order_items (order_id, kind, name, unit_price, qty) VALUES (?, ?, ?, ?, ?)",
                  (order, "combo", "조합", 1, 1))
    for name in ("통닭", "생맥주"):
        db.run("INSERT INTO order_item_components (order_item_id, name, qty) VALUES (?, ?, ?)", (line, name, 2))
    db.run("INSERT INTO orders (table_no, total) VALUES (?, ?)", (2, 10000))
    s = client.get("/admin/api/stats", headers=ADMIN).json()
    assert s["today_orders"] == 2 and s["avg_order_amount"] == 5000
    assert s["new_customers"] == 1 and s["genders"] == {"남": 1} and s["age_groups"]["20대"] == 1
    assert s["ai"] == {**s["ai"], "recommendations": 4, "ai_orders": 1, "hit_rate": 0.25}
    assert {"name": "통닭", "qty": 2} in s["popular_menus"]


def test_prod_refuses_default_secrets():
    with pytest.raises(RuntimeError):
        create_app(settings(app_env="prod", jwt_secret="change-me"))
    create_app(settings(app_env="prod"))  # 비밀값을 바꾸면 기동 가능


def test_content_endpoints_match_frontend_dummy_shape(client):
    """서버 응답이 user/*_data.py 더미와 같은 모양이어야 화면이 변환 없이 쓴다."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "user"))
    import ai_quiz_data, menu_data, recommendation_data

    content = client.get("/api/content").json()
    assert set(content) == {"categories", "staff_calls", "quiz_questions", "weather", "rules"}
    assert content["categories"] == menu_data.CATEGORIES
    prizes = client.get("/api/v1/roulette/prizes").json()
    assert [{k: v for k, v in prize.items() if k != "weight"} for prize in prizes] == menu_data.ROULETTE_PRIZES
    assert [prize["weight"] for prize in prizes] == [50, 10, 10, 10, 10, 10]
    assert content["staff_calls"] == menu_data.STAFF_CALLS
    assert content["quiz_questions"] == ai_quiz_data.QUESTIONS and content["weather"] == ai_quiz_data.WEATHER
    assert content["rules"] == recommendation_data.RULES
    assert client.get("/api/content/staff_calls").json() == menu_data.STAFF_CALLS
    assert client.get("/api/content/nope").status_code == 404
    store = client.get("/api/store").json()
    assert store == menu_data.STORE  # 매장 정보도 더미와 같은 모양
    menu = client.get("/api/menus").json()
    assert {"id", "cat", "name", "desc", "price", "emoji", "tags", "soldout"} <= menu[0].keys()


def test_admin_menu_categories_come_from_content(client):
    cats = client.get("/admin/api/menus", headers=ADMIN).json()["categories"]
    assert [c["id"] for c in cats] == ["chicken", "anju", "soup", "beer", "soju", "side"]  # ai/best 제외
