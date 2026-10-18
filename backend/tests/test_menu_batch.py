"""기존 메뉴 PUT 경로의 여러 행 일괄 저장과 트랜잭션을 확인한다."""

from fastapi.testclient import TestClient

ADMIN_API_PREFIX = "/admin/api"
from tests.conftest import ADMIN


MENUS_URL = f"{ADMIN_API_PREFIX}/menus"


def _menu_map(client):
    """관리자 목록에서 메뉴 ID별 현재 값을 가져온다."""
    response = client.get(MENUS_URL, headers=ADMIN)
    assert response.status_code == 200
    return {menu["id"]: menu for menu in response.json()["menus"]}


def test_menu_put_accepts_multiple_partial_menu_fields_and_reads_them_back(client):
    before = _menu_map(client)
    items = [
        {"id": "c1", "price": 19000, "desc": "설명 수정", "soldout": True},
        {"id": "c2", "weight": 75, "set_ok": False},
    ]

    response = client.put(f"{MENUS_URL}/c1", headers=ADMIN, json=items)

    assert response.status_code == 200
    assert response.json()["saved"] == 2
    after = _menu_map(client)
    assert after["c1"]["price"] == 19000
    assert after["c1"]["desc"] == "설명 수정"
    assert after["c1"]["soldout"] is True
    assert after["c2"]["weight"] == 75
    assert after["c2"]["set_ok"] is False
    assert after["c1"]["name"] == before["c1"]["name"]
    assert after["c2"]["price"] == before["c2"]["price"]
    guest = {menu["id"]: menu for menu in client.get("/api/menus").json()}
    assert guest["c1"]["price"] == 19000 and guest["c2"]["weight"] == 75


def test_menu_put_batch_can_create_a_menu_with_an_existing_update(client):
    response = client.put(
        f"{MENUS_URL}/c1",
        headers=ADMIN,
        json=[
            {"id": "c1", "weight": 80},
            {"id": "batch-new-menu", "name": "일괄 신메뉴", "cat": "anju", "price": 8000},
        ],
    )

    assert response.status_code == 200
    menus = _menu_map(client)
    assert menus["c1"]["weight"] == 80
    assert menus["batch-new-menu"]["name"] == "일괄 신메뉴"
    assert menus["batch-new-menu"]["cat"] == "anju"


def test_menu_put_batch_updates_and_deletes_together(client):
    before = _menu_map(client)
    response = client.put(
        f"{MENUS_URL}/c1",
        headers=ADMIN,
        json=[{"id": "c1", "price": 19000}, {"id": "c2", "delete": True}],
    )

    assert response.status_code == 200
    assert response.json()["saved"] == 1 and response.json()["deleted"] == 1
    after = _menu_map(client)
    assert after["c1"]["price"] == 19000
    assert "c2" not in after


def test_menu_put_rejects_empty_duplicate_or_missing_ids(client):
    for items in ([], [{"id": "c1", "weight": 20}, {"id": "c1", "price": 10000}], [{"price": 10000}]):
        response = client.put(f"{MENUS_URL}/c1", headers=ADMIN, json=items)
        assert response.status_code == 422
    mismatch = client.put(f"{MENUS_URL}/c2", headers=ADMIN, json=[{"id": "c1", "weight": 20}])
    assert mismatch.status_code == 422


def test_menu_put_batch_rejects_unknown_delete_without_saving_other_rows(client):
    before = _menu_map(client)
    response = client.put(
        f"{MENUS_URL}/c1",
        headers=ADMIN,
        json=[{"id": "c1", "price": 19000}, {"id": "missing-menu", "delete": True}],
    )

    assert response.status_code == 404
    assert _menu_map(client)["c1"]["price"] == before["c1"]["price"]


def test_menu_put_rejects_invalid_later_row_without_changing_earlier_row(client):
    before = _menu_map(client)

    response = client.put(
        f"{MENUS_URL}/c1",
        headers=ADMIN,
        json=[{"id": "c1", "price": 19000}, {"id": "c2", "cat": "missing-category"}],
    )

    assert response.status_code == 422
    after = _menu_map(client)
    assert after["c1"]["price"] == before["c1"]["price"]
    assert after["c2"]["cat"] == before["c2"]["cat"]


def test_menu_put_batch_rolls_back_when_database_rejects_a_later_row(client):
    db = client.app.state.db
    before = _menu_map(client)
    # 두 번째 행에서 DB 오류를 내 첫 번째 행까지 롤백되는지 확인한다.
    db.script(
        "CREATE TRIGGER reject_c2_price BEFORE UPDATE OF price ON menus "
        "WHEN OLD.id='c2' BEGIN SELECT RAISE(ABORT, 'test menu failure'); END;"
    )
    with TestClient(client.app, raise_server_exceptions=False) as no_raise_client:
        response = no_raise_client.put(
            f"{MENUS_URL}/c1",
            headers=ADMIN,
            json=[{"id": "c1", "price": 19000}, {"id": "c2", "price": 21000}],
        )

    assert response.status_code == 500
    after = _menu_map(client)
    assert after["c1"]["price"] == before["c1"]["price"]
    assert after["c2"]["price"] == before["c2"]["price"]


def test_menu_put_batch_rolls_back_update_when_database_rejects_a_delete(client):
    db = client.app.state.db
    before = _menu_map(client)
    # 삭제 단계에서 오류를 내면 앞서 수행한 다른 메뉴 수정도 함께 취소한다.
    db.script(
        "CREATE TRIGGER reject_c2_delete BEFORE DELETE ON menus "
        "WHEN OLD.id='c2' BEGIN SELECT RAISE(ABORT, 'test menu delete failure'); END;"
    )
    with TestClient(client.app, raise_server_exceptions=False) as no_raise_client:
        response = no_raise_client.put(
            f"{MENUS_URL}/c1",
            headers=ADMIN,
            json=[{"id": "c1", "price": 19000}, {"id": "c2", "delete": True}],
        )

    assert response.status_code == 500
    after = _menu_map(client)
    assert after["c1"]["price"] == before["c1"]["price"]
    assert "c2" in after


def test_menu_put_batch_requires_admin(client):
    response = client.put(f"{MENUS_URL}/c1", json=[{"id": "c1", "weight": 90}])

    assert response.status_code == 401
