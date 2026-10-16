from tests.conftest import login


def _my_id(client, headers):
    return client.get("/api/members/me", headers=headers).json()["id"]


def _box(client, member_id):
    return client.app.state.coupons.for_member(member_id)


def _spin(client, headers, table_no=1, **prize):
    body = {"member_id": _my_id(client, headers), "prize": "전 메뉴 5% 할인", "kind": "discount", "percent": 5,
            "emoji": "🎟️", **prize}
    return client.put(f"/api/tables/{table_no}/logins/prize", headers=headers, json=body)


def test_roulette_win_goes_into_coupon_box_and_is_listed(client):
    h = login(client, "가")
    r = _spin(client, h)
    assert r.status_code == 200 and r.json()["coupon"]["used_at"] is None
    mid = _my_id(client, h)
    box = _box(client, mid)  # GET /api/v1/coupons 는 더미라 저장소로 직접 확인한다
    assert [(c["kind"], c["percent"], c["label"], c["used_at"]) for c in box] == [("discount", 5, "전 메뉴 5% 할인", None)]
    assert [c["nickname"] for c in client.app.state.coupons.for_members([mid])] == ["가"]


def test_free_coupon_needs_item_and_discount_coupon_needs_percent(client):
    h = login(client, "가")
    assert _spin(client, h, kind="free", percent=None).status_code == 422  # item_id 없음
    assert _spin(client, h, percent=None).status_code == 422               # percent 없음
    assert _box(client, _my_id(client, h)) == []                           # 실패한 시도는 쿠폰을 만들지 않는다


def test_one_spin_per_member_per_day_even_at_another_table(client):
    h = login(client, "가")
    assert _spin(client, h).status_code == 200
    assert _spin(client, h).status_code == 409  # 같은 테이블 두 번째
    # 같은 날 다른 테이블: 그 테이블에 로그인 기록이 있어야 요청할 수 있으므로 기록을 직접 만든 뒤 시도한다
    mid = _my_id(client, h)
    c = client.app.state
    c.tablet_logins.record(2, mid, "가", eligible=not c.coupons.issued_today(mid))
    assert client.get("/api/tables/2/logins", headers=h).json()[0]["eligible"] is False  # 오늘은 룰렛 기회 없음
    assert _spin(client, h, table_no=2).status_code == 409


def test_next_day_member_can_spin_again(client):
    h = login(client, "가")
    assert _spin(client, h).status_code == 200
    mid = _my_id(client, h)
    client.app.state.coupons.db.run("UPDATE coupons SET issued_at='2000-01-01T00:00:00+00:00' WHERE member_id=?", (mid,))
    client.app.state.tablet_logins.db.run("DELETE FROM table_logins")  # 하루가 지나 로그인 기록도 만료됐다고 가정
    h2 = login(client, "가")
    assert client.get("/api/tables/1/logins", headers=h2).json()[0]["eligible"] is True
    assert _spin(client, h2).status_code == 200
    assert len(_box(client, mid)) == 2


def test_order_marks_coupon_used_only_for_tablet_members(client):
    a, b = login(client, "가"), login(client, "나")
    cid = _spin(client, a).json()["coupon"]["id"]
    order = {"table_no": 1, "lines": [{"id": "a1", "name": "치킨", "unit": 10000, "qty": 1}], "total": 9500}
    # 쿠폰을 받은 회원이 아닌 같은 테이블 회원 b 가 주문에 써도 된다 (한 테이블에서 같이 쓰는 쿠폰함)
    r = client.post("/api/orders", headers=b, json={**order, "coupon_ids": [cid, 9999]})
    assert r.status_code == 201 and r.json()["used_coupon_ids"] == [cid]
    box = _box(client, _my_id(client, a))
    assert box[0]["used_at"] and box[0]["used_order_id"] == r.json()["no"]
    # 이미 쓴 쿠폰은 다시 쓸 수 없다
    again = client.post("/api/orders", headers=b, json={**order, "coupon_ids": [cid]})
    assert again.json()["used_coupon_ids"] == []
    # 비회원 주문은 쿠폰을 쓸 수 없다
    assert client.post("/api/orders", json={**order, "coupon_ids": [cid]}).json()["used_coupon_ids"] == []


def test_coupon_box_requires_login_and_tablet_membership(client):
    h = login(client, "가")
    assert client.get("/api/v1/coupons").status_code == 401
    assert client.get("/api/tables/2/coupons", headers=h).status_code == 403
