from tests.conftest import login


def test_tablet_login_records_survive_and_prize_is_once_per_member(client):
    a, b = login(client, "가"), login(client, "나")  # 둘 다 table_no=1 에서 로그인
    other = login(client, "다")
    rows = client.get("/api/tables/1/logins", headers=b).json()
    assert [r["nickname"] for r in rows] == ["가", "나", "다"] and all(r["eligible"] and r["prize"] is None for r in rows)

    me_a = client.get("/api/members/me", headers=a).json()["id"]
    r = client.put("/api/tables/1/logins/prize", headers=other, json={"member_id": me_a, "prize": "10% 할인"})
    assert r.status_code == 200
    again = client.put("/api/tables/1/logins/prize", headers=other, json={"member_id": me_a, "prize": "소주 1병"})
    assert again.status_code == 409  # 회원당 1회
    assert [r["prize"] for r in client.get("/api/tables/1/logins", headers=a).json()] == ["10% 할인", None, None]


def test_tablet_logins_are_private_to_that_tablet(client):
    h = login(client, "가")
    assert client.get("/api/tables/2/logins", headers=h).status_code == 403  # 다른 테이블 기록은 못 본다
    assert client.get("/api/tables/1/logins").status_code == 401
