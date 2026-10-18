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
