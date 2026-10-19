"""석원 TODO 2: 관리자 룰렛 설정 저장과 손님 조회 API."""

from tests.conftest import ADMIN


def _prizes():
    return [
        {"label": "전 메뉴<br><b>10% 할인</b>", "short": "전 메뉴 10% 할인", "emoji": "🎟️",
         "color": "#112233", "kind": "discount", "percent": 10, "weight": 50},
        {"label": "계란말이<br><b>서비스</b>", "short": "계란말이 서비스", "emoji": "🥚",
         "color": "#abcdef", "kind": "free", "item_id": "a4", "weight": 50},
    ]


def test_save_then_public_read_keeps_order(client):
    response = client.put("/admin/api/owner/roulette/prizes", headers=ADMIN, json=_prizes())
    assert response.status_code == 200
    assert client.get("/api/v1/roulette/prizes").json() == response.json()
    assert [prize["weight"] for prize in response.json()] == [50.0, 50.0]


def test_put_requires_admin(client):
    assert client.put("/admin/api/owner/roulette/prizes", json=_prizes()).status_code == 401
    assert client.put("/api/v1/owner/roulette/prizes", json=_prizes()).status_code == 401


def test_saves_typed_probabilities(client):
    # 0% 및 100% 경계와 1% 단위 값을 양쪽 저장 경로에서 그대로 유지한다.
    for path in ("/admin/api/owner/roulette/prizes", "/api/v1/owner/roulette/prizes"):
        for weights in ((55, 45), (1, 99), (0, 100)):
            body = [{**prize, "weight": weight} for prize, weight in zip(_prizes(), weights)]
            response = client.put(path, headers=ADMIN, json=body)
            assert response.status_code == 200
            assert [prize["weight"] for prize in client.get("/api/v1/roulette/prizes").json()] == list(weights)


def test_drink_service_options_are_allowed(client):
    for menu_id in ("d1", "j1", "b1"):
        body = [_prizes()[0], {**_prizes()[1], "item_id": menu_id}]
        assert client.put("/admin/api/owner/roulette/prizes", headers=ADMIN, json=body).status_code == 200


def test_rejects_bad_prizes(client):
    bad_cases = [
        _prizes()[:1],
        _prizes() * 5,
        [{**prize, "weight": 0} for prize in _prizes()],
        [{**_prizes()[0], "weight": 55.5}, {**_prizes()[1], "weight": 44.5}],
        [{**_prizes()[0], "weight": -1}, {**_prizes()[1], "weight": 101}],
        [{**_prizes()[0], "weight": 51}, {**_prizes()[1], "weight": 50}],
        [{**_prizes()[0], "weight": 40}, {**_prizes()[1], "weight": 40}],
        [{**_prizes()[0], "percent": None}, _prizes()[1]],
        [_prizes()[0], {**_prizes()[1], "item_id": "missing"}],
        [_prizes()[0], {**_prizes()[1], "item_id": "c1"}],  # 한 마리 치킨 같은 메인 메뉴는 서비스 대상이 아니다.
    ]
    for body in bad_cases:
        assert client.put("/admin/api/owner/roulette/prizes", headers=ADMIN, json=body).status_code == 422
