"""더미로 돌려주는 GET 엔드포인트(app/dummy.py)가 화면이 쓰는 모양을 유지하는지 확인한다.

실제 DB 로 바꾼 엔드포인트는 여기서 빼고 자기 테스트를 만든다."""

from app import dummy
from tests.conftest import ADMIN, login


def test_user_get_dummies(client):
    assert {"name", "branch", "slogan", "tables"} <= client.get("/api/v1/store").json().keys()
    assert set(client.get("/api/content").json()) == {"categories", "roulette_prizes", "staff_calls",
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
    assert {"id", "ts", "table_no", "items", "done"} <= client.get("/admin/api/calls", headers=ADMIN).json()[0].keys()
    stats = client.get("/admin/api/stats", headers=ADMIN).json()
    assert stats["today_orders"] > 0 and stats["popular_menus"] and stats["ai"]["recommendations"] == 9


def test_every_listed_dummy_function_exists():
    for names in dummy.DUMMY_ENDPOINTS.values():
        for n in names.split(" / "):
            assert callable(getattr(dummy, n))
