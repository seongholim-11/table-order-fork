"""재현 TODO 3-2: 서버가 룰렛 결과를 결정하고 상태를 저장하는지 확인한다."""

from tests.conftest import login


def test_status_and_play_are_server_driven(client, monkeypatch):
    first = login(client, "첫손님")
    second = login(client, "둘째손님")
    first_id = client.get("/api/members/me", headers=first).json()["id"]
    second_id = client.get("/api/members/me", headers=second).json()["id"]

    client.app.state.roulette_prizes.replace([
        {"label": "꽝", "short": "꽝", "emoji": "🙃", "color": "#111111", "kind": "discount",
         "percent": 5, "weight": 0},
        {"label": "할인", "short": "10% 할인", "emoji": "🎟️", "color": "#222222", "kind": "discount",
         "percent": 10, "weight": 1},
    ])
    monkeypatch.setattr("app.routers.roulette.random.choices", lambda *args, **kwargs: [1])

    status = client.get("/api/v1/roulette/status", params={"table_no": 1}, headers=first)
    assert status.status_code == 200 and status.json()["remaining"] == 2
    assert {row["id"] for row in status.json()["members"]} == {first_id, second_id}

    played = client.post("/api/v1/roulette/plays", headers=first,
                         json={"table_no": 1, "member_id": first_id})
    assert played.status_code == 201 and played.json()["index"] == 1
    assert played.json()["prize"]["percent"] == 10 and played.json()["coupon"]["percent"] == 10
    assert client.post("/api/v1/roulette/plays", headers=first,
                       json={"table_no": 1, "member_id": first_id}).status_code == 409

    status = client.get("/api/v1/roulette/status", params={"table_no": 1}, headers=second)
    assert status.json()["remaining"] == 1
