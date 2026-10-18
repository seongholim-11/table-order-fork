"""석원 TODO 1: 직원 호출 항목·등록·관리자 완료 처리의 DB 흐름을 확인한다."""

import sqlite3

import pytest

from tests.conftest import ADMIN


def test_staff_call_items_are_seeded_sorted_and_unique(client):
    expected = ["💧 물", "🥄 수저·젓가락", "🍽️ 앞접시", "🧻 휴지·물티슈",
                "🧊 얼음", "🔥 가스불 점검", "💳 계산 요청", "🙋 기타 문의"]
    assert client.get("/api/v1/staff-call-items").json() == expected

    # 운영 중 목록이 비어도 다음 조회에서 전용 시드로 복구되어 호출 창이 비지 않는다.
    client.app.state.db.run("DELETE FROM staff_call_items")
    assert client.get("/api/v1/staff-call-items").json() == expected
    with pytest.raises(sqlite3.IntegrityError):
        client.app.state.db.run(
            "INSERT INTO staff_call_items (label, sort_order) VALUES (?, ?)", ("💧 물", 99))


def test_guest_can_create_call_with_new_and_legacy_paths(client):
    new = client.post("/api/v1/staff-calls", json={"table_no": 7, "items": ["💧 물", "🥄 수저·젓가락"]})
    legacy = client.post("/api/calls", json={"table_no": 3, "items": ["🍽️ 앞접시"]})
    assert new.status_code == legacy.status_code == 201
    assert new.json()["id"] != legacy.json()["id"]
    assert client.post("/api/v1/staff-calls", json={"table_no": 1, "items": []}).status_code == 422
    assert client.post("/api/v1/staff-calls", json={"table_no": 0, "items": ["💧 물"]}).status_code == 422

    saved = client.app.state.shop.call(new.json()["id"])
    assert saved["table_no"] == 7 and saved["items"] == ["💧 물", "🥄 수저·젓가락"]
    assert saved["done"] is False


def test_admin_lists_latest_and_done_is_idempotent(client):
    ids = [client.post("/api/v1/staff-calls", json={"table_no": table, "items": [f"요청 {table}"]}).json()["id"]
           for table in (1, 2, 3)]
    # 생성 시각이 같은 DB도 id 역순으로 최신 순서를 안정적으로 보장한다.
    rows = client.get("/admin/api/calls", headers=ADMIN)
    assert rows.status_code == 200
    assert [row["id"] for row in rows.json()] == list(reversed(ids))
    assert all({"id", "table_no", "items", "ts", "done"} == set(row) for row in rows.json())

    first = client.post(f"/admin/api/calls/{ids[1]}/done", headers=ADMIN)
    second = client.post(f"/admin/api/calls/{ids[1]}/done", headers=ADMIN)
    assert first.status_code == second.status_code == 200
    assert first.json()["done"] is second.json()["done"] is True
    assert client.post("/admin/api/calls/999999/done", headers=ADMIN).status_code == 404


def test_admin_call_api_requires_token(client):
    assert client.get("/admin/api/calls").status_code == 401
    assert client.post("/admin/api/calls/1/done").status_code == 401
