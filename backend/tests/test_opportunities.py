"""석원 TODO 3: DB 기반 관리자 마케팅 추천 API 테스트."""

from datetime import datetime, timedelta

from app.services.grades import KST
from tests.conftest import ADMIN, login, set_profile

URL = "/admin/api/marketing/opportunities"
GROWTH_URL = "/admin/api/marketing/growth-performance"


def test_empty_data_returns_one_guide_card_and_requires_admin(client):
    assert client.get(URL).status_code == 401
    result = client.get(URL, headers=ADMIN).json()
    assert result == {
        "items": [{
            "title": "데이터를 더 모아 볼까요?",
            "why": "아직 주문·회원 데이터가 적어 추천할 근거가 부족해요.",
            "action": "주문이 쌓이면 이곳에 맞춤 마케팅 방법이 나타나요.",
        }],
        "page": 1,
        "pages": 1,
    }
    assert client.get(f"{URL}?round=-1", headers=ADMIN).status_code == 422


def test_cards_use_db_facts_and_round_cycles_four_at_a_time(client):
    """여러 규칙이 켜지는 DB 자료를 넣어 다음 묶음과 처음 순환까지 확인한다."""
    now = datetime.now(KST)
    profiles = [
        ("휴면손님", 2, now - timedelta(days=40), True),
        ("단골손님", 7, now, True),
        ("신규손님", 1, now, False),
    ]
    member_ids = []
    for nickname, visits, last_visit, consent in profiles:
        headers = login(client, nickname, agree=consent)
        member_id = client.get("/api/members/me", headers=headers).json()["id"]
        set_profile(client, headers, phone="01000000000", consent=consent)
        client.app.state.db.run(
            "UPDATE members SET visit_count=?, last_visit_at=? WHERE id=?",
            (visits, last_visit.isoformat(), member_id),
        )
        member_ids.append(member_id)

    db = client.app.state.db
    db.run(
        "INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?, ?, ?, ?, ?)",
        (3, member_ids[1], 18000, 1, now.replace(hour=19).isoformat()),
    )
    order_id = db.one("SELECT MAX(id) AS id FROM orders")["id"]
    db.run(
        "INSERT INTO order_items (order_id, menu_id, kind, name, option_label, unit_price, qty) "
        "VALUES (?, ?, 'menu', ?, '', ?, ?)",
        (order_id, "c1", "역전 옛날통닭", 18000, 1),
    )
    db.run("UPDATE menus SET is_soldout=1 WHERE id='a11'")
    for _ in range(10):
        db.run("INSERT INTO recommendation_events (table_no) VALUES (3)")

    first = client.get(f"{URL}?round=0", headers=ADMIN).json()
    second = client.get(f"{URL}?round=1", headers=ADMIN).json()
    wrapped = client.get(f"{URL}?round={first['pages']}", headers=ADMIN).json()

    assert first["pages"] >= 2 and len(first["items"]) == len(second["items"]) == 4
    assert first["items"] != second["items"] and wrapped["items"] == first["items"]
    assert all(set(card) == {"title", "why", "action"} for card in first["items"] + second["items"])
    assert any("휴면 고객 1명" in card["title"] for card in first["items"] + second["items"])


def test_growth_performance_uses_db_and_one_month_formula(client):
    """화면 더미가 아니라 orders DB의 최초 AI 주문 전후를 같은 30일 기준으로 계산한다."""
    assert client.get(GROWTH_URL).status_code == 401
    db = client.app.state.db
    start = datetime.now(KST).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=3)
    for offset, amount, ai in ((0, 100, 0), (1, 100, 0), (2, 200, 1), (3, 200, 1)):
        db.run("INSERT INTO orders (table_no, total, ai_combo, created_at) VALUES (1, ?, ?, ?)",
               (amount, ai, (start + timedelta(days=offset)).isoformat()))
    result = client.get(GROWTH_URL, headers=ADMIN).json()
    assert result["baseline_monthly"] == 3_000
    assert result["performance_monthly"] == 6_000
    assert result["monthly_growth"] == 3_000
    assert result["ai_monthly_revenue"] == 6_000
    assert result["monthly_growth"] == result["performance_monthly"] - result["baseline_monthly"]

