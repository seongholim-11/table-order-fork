"""더미로 돌려주는 엔드포인트(app/dummy.py, GET 과 쓰기)가 화면이 쓰는 모양을 유지하는지 확인한다.

실제 DB 로 바꾼 엔드포인트는 여기서 빼고 자기 테스트를 만든다."""

from app import dummy
from tests.conftest import ADMIN, login


def test_user_get_dummies(client):
    assert {"name", "branch", "slogan", "tables"} <= client.get("/api/v1/store").json().keys()
    assert set(client.get("/api/content").json()) == {"categories", "staff_calls",
                                                       "quiz_questions", "weather", "rules"}
    assert client.get("/api/content/categories").json()[0]["id"] and client.get("/api/content/nope").status_code == 404
    menus = client.get("/api/menus").json()
    assert len(menus) == 60 and {"id", "cat", "name", "desc", "price", "soldout"} <= menus[0].keys()


def test_coupon_dummies(client):
    h = login(client, "가")
    box = client.get("/api/v1/coupons", headers=h).json()
    assert box == client.get("/api/coupons", headers=h).json() and {"id", "kind", "label", "used_at"} <= box[0].keys()
    assert "nickname" in client.get("/api/tables/1/coupons", headers=h).json()[0]
    assert client.get("/api/tables/2/coupons", headers=h).status_code == 403  # 이 태블릿에 로그인한 기록이 없으면 더미여도 막는다


def test_admin_get_dummies(client):
    menus = client.get("/admin/api/menus", headers=ADMIN).json()
    assert [c["id"] for c in menus["categories"]] == ["chicken", "anju", "soup", "beer", "soju", "side"] and menus["menus"]
    orders = client.get("/admin/api/orders", headers=ADMIN).json()
    assert {"id", "ts", "table_no", "total", "lines", "ai_combo", "member_id", "nickname"} <= orders[0].keys()
    mine = client.get("/admin/api/orders", headers=ADMIN, params={"member_id": 1}).json()
    assert mine and all(o["member_id"] == 1 for o in mine)
    stats = client.get("/admin/api/stats", headers=ADMIN).json()
    assert stats["today_orders"] > 0 and stats["popular_menus"] and stats["ai"]["recommendations"] == 9


def test_every_listed_dummy_function_exists():
    for names in dummy.DUMMY_ENDPOINTS.values():
        for n in names.split(" / "):
            assert callable(getattr(dummy, n))


# ---- 쓰기(POST/PUT/DELETE)도 저장 없이 화면이 깨지지 않는 성공 응답을 돌려준다 ----
def test_user_write_dummies(client):
    h = login(client, "가")
    line = {"id": "c1", "name": "역전 옛날통닭", "unit": 18000, "qty": 2}
    r = client.post("/api/orders", headers=h, json={"table_no": 5, "lines": [line], "total": 36000, "coupon_ids": [7]})
    assert r.status_code == 201 and r.json() == {"no": r.json()["no"], "ai_combo": False, "used_coupon_ids": [7]}
    assert client.post("/api/orders", json={"table_no": 6, "lines": [line], "total": 36000}).status_code == 201  # 비회원
    assert client.post("/api/orders", json={"table_no": 6, "lines": [], "total": 0}).status_code == 422  # 스키마 검증은 그대로
    assert client.post("/api/calls", json={"table_no": 3, "items": ["💧 물"]}).json()["id"]
    assert client.post("/api/recommendations", json={"table_no": 1, "params": {}, "combo_ids": ["classic"]}).json()["id"]
    me = client.get("/api/members/me", headers=h).json()["id"]
    prize = {"member_id": me, "prize": "10% 할인", "kind": "discount", "percent": 10, "emoji": "🎟️"}
    r = client.put("/api/tables/1/logins/prize", headers=h, json=prize)
    assert r.status_code == 200 and r.json()["ok"] and r.json()["coupon"]["label"] == "10% 할인"
    assert client.put("/api/tables/1/logins/prize", headers=h, json={"member_id": me, "prize": "꽝"}).json()["coupon"] is None


def test_admin_write_dummies(client):
    saved = client.put("/admin/api/menus/c2", headers=ADMIN, json={"weight": 90, "soldout": True}).json()
    assert saved["id"] == "c2" and saved["weight"] == 90 and saved["soldout"] is True and saved["name"]
    assert client.put("/admin/api/menus/new1", headers=ADMIN, json={"name": "신메뉴", "cat": "anju", "price": 9000}).json()["name"] == "신메뉴"
    assert client.put("/admin/api/menus/c2", headers=ADMIN, json={"weight": 101}).status_code == 422  # 스키마 검증은 그대로
    assert client.delete("/admin/api/menus/c2", headers=ADMIN).status_code == 204
    assert client.put("/admin/api/content/staff_calls", headers=ADMIN, json=["💧 물"]).json() == ["💧 물"]
    for method, path in (("put", "/admin/api/menus/c2"), ("delete", "/admin/api/menus/c2")):
        assert getattr(client, method)(path).status_code in (401, 422)  # 인증은 그대로
