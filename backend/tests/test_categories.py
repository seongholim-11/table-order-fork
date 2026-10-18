"""카테고리 API의 정렬, 검증, 메뉴 참조 규칙을 확인한다."""

from tests.conftest import ADMIN
ADMIN_API_PREFIX = "/admin/api"


def _add_category(client, name="테스트 카테고리"):
    """각 테스트에서 새 카테고리를 만들고 응답을 돌려준다."""
    return client.post(
        f"{ADMIN_API_PREFIX}/categories",
        headers=ADMIN,
        json={"name": name, "icon": "🍢", "colors": ["#112233", "#445566"]},
    )


def test_guest_categories_keep_screen_shape_and_sort_order(client):
    db = client.app.state.db
    # DB 표시 순서를 일부러 바꿔 API가 seed 입력 순서가 아니라 sort_order를 따르는지 확인한다.
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (0, "beer"))
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (10, "chicken"))
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (20, "anju"))

    response = client.get("/api/categories")

    assert response.status_code == 200
    categories = response.json()
    assert [category["id"] for category in categories].index("beer") < [
        category["id"] for category in categories
    ].index("chicken") < [category["id"] for category in categories].index("anju")
    assert all(
        {"id", "icon", "name", "colors"} <= category.keys()
        and isinstance(category["colors"], list)
        and len(category["colors"]) == 2
        for category in categories
    )


def test_admin_menu_categories_include_menu_counts(client):
    response = client.get(f"{ADMIN_API_PREFIX}/categories", headers=ADMIN)

    assert response.status_code == 200
    payload = response.json()

    response = client.get(f"{ADMIN_API_PREFIX}/menus", headers=ADMIN)
    menus = response.json()["menus"]

    for cat in payload:
        cat_cnt = sum(1 for menu in menus if menu["cat"] == cat["id"])
        assert cat_cnt == cat["menu_count"]


def test_admin_categories_include_virtual_flags_and_follow_database_order(client):
    db = client.app.state.db
    # 표시 순서를 바꿔 관리자 목록도 DB의 sort_order를 따르는지 확인한다.
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (0, "beer"))
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (10, "chicken"))
    db.run("UPDATE categories SET sort_order=? WHERE id=?", (20, "anju"))

    response = client.get(f"{ADMIN_API_PREFIX}/categories", headers=ADMIN)

    assert response.status_code == 200
    categories = response.json()
    ids = [category["id"] for category in categories]
    assert ids.index("beer") < ids.index("chicken") < ids.index("anju")
    flags = {category["id"]: category["is_virtual"] for category in categories}
    assert flags["ai"] is True and flags["best"] is True
    assert flags["chicken"] is False
    assert all("menu_count" in category for category in categories)



def test_category_create_rejects_empty_and_duplicate_names(client):
    empty = client.post(
        f"{ADMIN_API_PREFIX}/categories",
        headers=ADMIN,
        json={"name": "   ", "icon": "🍢", "colors": ["#112233", "#445566"]},
    )
    assert empty.status_code == 422

    created = _add_category(client, "중복 검사 카테고리")
    assert created.status_code == 201
    assert created.json()["name"] == "중복 검사 카테고리"
    assert created.json()["colors"] == ["#112233", "#445566"]

    duplicate = _add_category(client, "중복 검사 카테고리")
    assert duplicate.status_code == 409


def test_new_category_is_appended_and_shared_with_guest_list(client):
    before = client.get("/api/categories").json()
    created = _add_category(client, "마지막 카테고리")

    assert created.status_code == 201
    category_id = created.json()["id"]
    guest_categories = client.get("/api/categories").json()
    admin_categories = client.get(f"{ADMIN_API_PREFIX}/categories", headers=ADMIN).json()
    assert guest_categories[-1]["id"] == category_id
    assert {category["id"] for category in before} < {category["id"] for category in guest_categories}
    assert next(category for category in admin_categories if category["id"] == category_id)["menu_count"] == 0


def test_category_patch_updates_fields_and_delete_removes_empty_category(client):
    created = _add_category(client, "수정 전 이름")
    assert created.status_code == 201
    category_id = created.json()["id"]

    updated = client.patch(
        f"{ADMIN_API_PREFIX}/categories/{category_id}",
        headers=ADMIN,
        json={"name": "수정 후 이름", "icon": "🍲"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "수정 후 이름"
    assert updated.json()["icon"] == "🍲"
    assert updated.json()["colors"] == ["#112233", "#445566"]

    deleted = client.delete(f"{ADMIN_API_PREFIX}/categories/{category_id}", headers=ADMIN)
    assert deleted.status_code == 204
    remaining = client.get("/api/categories").json()
    assert category_id not in {category["id"] for category in remaining}


def test_category_with_menu_cannot_be_deleted(client):
    created = _add_category(client, "메뉴 참조 카테고리")
    assert created.status_code == 201
    category_id = created.json()["id"]
    client.app.state.shop.save_menu(
        "category-linked-menu",
        {"cat": category_id, "name": "연결 메뉴", "price": 5000},
    )

    deleted = client.delete(f"{ADMIN_API_PREFIX}/categories/{category_id}", headers=ADMIN)

    assert deleted.status_code == 409
    assert category_id in {category["id"] for category in client.get("/api/categories").json()}


def test_virtual_categories_cannot_be_updated_or_deleted(client):
    for category_id in ("ai", "best"):
        updated = client.patch(
            f"{ADMIN_API_PREFIX}/categories/{category_id}",
            headers=ADMIN,
            json={"name": f"수정 금지 {category_id}"},
        )
        assert updated.status_code == 409

        deleted = client.delete(f"{ADMIN_API_PREFIX}/categories/{category_id}", headers=ADMIN)
        assert deleted.status_code == 409


def test_category_admin_routes_require_token(client):
    assert client.get(f"{ADMIN_API_PREFIX}/categories").status_code == 401
    assert client.post(
        f"{ADMIN_API_PREFIX}/categories",
        json={"name": "인증 검사", "icon": "🍢", "colors": ["#112233", "#445566"]},
    ).status_code == 401
    assert client.patch(f"{ADMIN_API_PREFIX}/categories/chicken", json={"name": "무단 수정"}).status_code == 401
    assert client.delete(f"{ADMIN_API_PREFIX}/categories/chicken").status_code == 401


def test_category_patch_and_delete_return_not_found_for_unknown_id(client):
    updated = client.patch(
        f"{ADMIN_API_PREFIX}/categories/missing-category",
        headers=ADMIN,
        json={"name": "없는 카테고리"},
    )
    deleted = client.delete(f"{ADMIN_API_PREFIX}/categories/missing-category", headers=ADMIN)

    assert updated.status_code == 404
    assert deleted.status_code == 404
