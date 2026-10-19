"""메뉴 시드와 손님 메뉴 조회를 확인한다."""


def test_menu_seed_and_user_list(client):
    menus = client.get("/api/menus").json()

    # 빈 DB에서 JSON 시드 60개를 읽고 화면이 사용하는 키와 자료형으로 돌려준다.
    assert len(menus) == 60
    assert {"id", "cat", "name", "desc", "price", "emoji", "tags", "soldout",
            "spicy", "weight", "set_ok", "image_url"} <= menus[0].keys()
    c2 = next(menu for menu in menus if menu["id"] == "c2")
    assert c2["soldout"] is False
    assert c2["price"] == 20000
    assert c2["weight"] == 50
    assert isinstance(c2["tags"], list)


def test_menu_store_saves_partial_updates_and_string_ids(client):
    shop = client.app.state.shop

    # 문자열 ID를 그대로 쓰며, 부분 수정은 전달한 필드만 바꾼다.
    saved = shop.save_menu("m3fa2b1", {"cat": "anju", "name": "테스트 안주", "price": 9000})
    assert saved["id"] == "m3fa2b1"
    assert saved["cat"] == "anju"

    updated = shop.save_menu("m3fa2b1", {"soldout": True})
    assert updated["name"] == "테스트 안주"
    assert updated["soldout"] is True
    assert shop.menu("m3fa2b1") == updated

    assert shop.delete_menu("m3fa2b1") is True
    assert shop.menu("m3fa2b1") is None
    assert shop.delete_menu("m3fa2b1") is False


def test_menu_seed_only_fills_an_empty_catalog(client, empty_menu_catalog):
    shop = client.app.state.shop
    assert shop.menus() == []

    # 최초 시드는 메뉴를 복구하고, 이후 시드는 관리자가 바꾼 값을 보존한다.
    shop.seed_menus()
    assert len(shop.menus()) == 60
    shop.save_menu("c2", {"price": 21000})
    shop.seed_menus()
    assert shop.menu("c2")["price"] == 21000


def test_menu_event_flag_defaults_and_saves(client):
    shop = client.app.state.shop

    # 시드에서는 기본 이벤트 메뉴(계란말이)만 체크되어 있고, 새 메뉴는 체크가 없는 상태로 시작한다.
    assert shop.menu("a4")["is_event"] is True
    assert shop.menu("c2")["is_event"] is False
    assert shop.save_menu("m-event", {"cat": "anju", "name": "이벤트 안주", "price": 1000})["is_event"] is False

    # 관리자 API 로 체크하고 해제할 수 있다.
    from tests.conftest import ADMIN
    response = client.put("/admin/api/menus/m-event", headers=ADMIN, json={"is_event": True})
    assert response.json()["is_event"] is True
    assert next(m for m in client.get("/admin/api/menus", headers=ADMIN).json()["menus"] if m["id"] == "m-event")["is_event"]
    assert client.put("/admin/api/menus/m-event", headers=ADMIN, json={"is_event": False}).json()["is_event"] is False


def test_menu_event_flag_works_before_migration(client):
    shop = client.app.state.shop

    # 운영 DB에 is_event 컬럼이 아직 없는 상황: 컬럼을 지워도 조회·저장이 죽지 않고 기본 메뉴만 이벤트로 본다.
    shop.db.run("ALTER TABLE menus DROP COLUMN is_event")
    shop._event_column_ok = False
    assert shop.menu("a4")["is_event"] is True
    assert shop.menu("c2")["is_event"] is False
    assert shop.save_menu("c2", {"is_event": True, "name": "치킨"})["name"] == "치킨"
    assert shop.menu("c2")["is_event"] is False
    assert client.app.state.roulette_prizes.service_menu_exists("a4") is True
    assert client.app.state.roulette_prizes.service_menu_exists("c2") is False
