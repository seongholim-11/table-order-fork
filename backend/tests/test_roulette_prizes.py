"""석원 TODO 2: 관리자 룰렛 설정 저장과 손님 조회 API."""

from tests.conftest import ADMIN


def _prizes():
    return [
        {"label": "전 메뉴<br><b>10% 할인</b>", "short": "전 메뉴 10% 할인", "emoji": "🎟️",
         "color": "#112233", "kind": "discount", "percent": 10, "weight": 3},
        {"label": "계란말이<br><b>서비스</b>", "short": "계란말이 서비스", "emoji": "🥚",
         "color": "#abcdef", "kind": "free", "item_id": "a4", "weight": 1},
    ]


def test_save_then_public_read_keeps_order(client):
    response = client.put("/admin/api/owner/roulette/prizes", headers=ADMIN, json=_prizes())
    assert response.status_code == 200
    assert client.get("/api/v1/roulette/prizes").json() == response.json()
    assert [prize["weight"] for prize in response.json()] == [3.0, 1.0]


def test_put_requires_admin(client):
    assert client.put("/admin/api/owner/roulette/prizes", json=_prizes()).status_code == 401
    assert client.put("/api/v1/owner/roulette/prizes", json=_prizes()).status_code == 401


def test_rejects_bad_prizes(client):
    bad_cases = [
        _prizes()[:1],
        _prizes() * 5,
        [{**prize, "weight": 0} for prize in _prizes()],
        [{**_prizes()[0], "percent": None}, _prizes()[1]],
        [_prizes()[0], {**_prizes()[1], "item_id": "missing"}],
    ]
    for body in bad_cases:
        assert client.put("/admin/api/owner/roulette/prizes", headers=ADMIN, json=body).status_code == 422
