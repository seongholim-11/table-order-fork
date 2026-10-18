def test_user_menu_list_returns_seeded_menus(client):
    response = client.get("/api/menus")

    assert response.status_code == 200
    menus = response.json()
    expected_fields = {
        "id", "cat", "name", "desc", "price", "emoji", "tags",
        "soldout", "spicy", "weight", "set_ok", "image_url",
    }
    assert len(menus) == 60
    assert all(expected_fields <= menu.keys() for menu in menus)
    assert all(isinstance(menu["tags"], list) for menu in menus)
    assert all(isinstance(menu["soldout"], bool) and isinstance(menu["set_ok"], bool) for menu in menus)
    # 품절 메뉴도 목록에서 빼지 않고 soldout 값으로 표시한다.
    assert any(menu["soldout"] for menu in menus)
