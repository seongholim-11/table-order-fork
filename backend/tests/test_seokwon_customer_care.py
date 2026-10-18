"""석원: 실제 DB의 재방문 기록으로 현장 손님 응대 제안을 만드는지 확인한다."""

from datetime import datetime, timedelta, timezone

from app.services.grades import KST
from tests.conftest import ADMIN


URL = "/admin/api/marketing/regular-preferences"


def _order(client, member_id: int, days_ago: int, menu_id: str, name: str, table: int) -> None:
    """테스트 DB에 방문일·테이블·메뉴가 서로 연결된 주문을 한 건 넣는다."""
    at = datetime.now(KST).replace(hour=19, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    db = client.app.state.db
    order_id = db.run(
        "INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
        (table, member_id, 15000, at.astimezone(timezone.utc).isoformat()),
    )
    db.run(
        "INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, kind) VALUES (?, ?, ?, 1, 15000, 'menu')",
        (order_id, menu_id, name),
    )


def test_second_visit_birthday_connects_previous_table_menu_and_current_table(client):
    """두 번째 방문부터 과거 자리·메뉴와 생일을 현재 테이블 응대에 연결한다."""
    db = client.app.state.db
    db.run("DELETE FROM menus")
    for menu_id, name in (("care-pajeon", "해물파전"), ("care-egg", "계란말이")):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, 'anju', ?, 15000)", (menu_id, name))
    today = datetime.now(KST).date()
    member = client.app.state.members.upsert_login(
        "care-birthday", "김민수", birthday=today.strftime("%m%d"), birth_year=today.year - 30,
    )
    db.run("UPDATE members SET visit_count=2 WHERE id=?", (member["id"],))
    _order(client, member["id"], 35, "care-pajeon", "해물파전", 13)
    _order(client, member["id"], 0, "care-egg", "계란말이", 7)

    response = client.get(URL, headers=ADMIN)
    assert response.status_code == 200
    row, = response.json()["preferences"]
    assert row["visit_count"] == 2 and row["today_table"] == 7
    assert "13번 테이블" in row["previous_visit"] and "해물파전" in row["previous_visit"]
    assert row["special_event"] == "birthday" and row["age"] == 30
    assert "생일" in row["care_reason"] and "서비스" in row["service_suggestion"]


def test_rainy_day_pajeon_history_creates_data_based_service_suggestion(client):
    """저장된 오늘 날씨와 과거 파전 주문이 모두 있을 때만 비 오는 날 제안을 만든다."""
    db = client.app.state.db
    db.run("DELETE FROM menus")
    for menu_id, name in (("care-pajeon", "해물파전"), ("care-egg", "계란말이")):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, 'anju', ?, 15000)", (menu_id, name))
    member = client.app.state.members.upsert_login("care-rain", "영희")
    db.run("UPDATE members SET visit_count=4 WHERE id=?", (member["id"],))
    _order(client, member["id"], 5, "care-pajeon", "해물파전", 13)
    _order(client, member["id"], 2, "care-pajeon", "해물파전", 9)
    _order(client, member["id"], 0, "care-egg", "계란말이", 4)
    today = datetime.now(KST).date()
    # 외부 API를 즉석 호출하지 않고 이미 DB에 저장된 오늘 날씨만 근거로 사용한다.
    client.app.state.external.store.save(today.isoformat(), "비 오는 18도 날씨", "")

    row, = client.get(URL, headers=ADMIN).json()["preferences"]
    assert row["special_event"] == "rainy_favorite"
    assert row["most_ordered_menu"] == "해물파전" and row["weather_text"] == "비 오는 18도 날씨"
    assert "해물파전" in row["care_reason"] and "서비스" in row["service_suggestion"]


def test_three_login_days_drive_frequent_visit_suggestion_even_with_two_orders(client):
    """한 주 방문 빈도는 주문 건수가 아니라 table_logins의 서로 다른 로그인 날짜로 계산한다."""
    db = client.app.state.db
    db.run("DELETE FROM menus")
    db.run("INSERT INTO menus (id, category_id, name, price) VALUES ('care-egg', 'anju', '계란말이', 15000)")
    member = client.app.state.members.upsert_login("care-frequent", "자주온손님")
    db.run("UPDATE members SET visit_count=3 WHERE id=?", (member["id"],))
    _order(client, member["id"], 2, "care-egg", "계란말이", 8)
    _order(client, member["id"], 0, "care-egg", "계란말이", 4)
    for days_ago, table in ((2, 8), (1, 6), (0, 4)):
        logged_at = datetime.now(KST) - timedelta(days=days_ago)
        db.run(
            "INSERT INTO table_logins (table_no, member_id, login_day, logged_in_at) VALUES (?, ?, ?, ?)",
            (table, member["id"], logged_at.date().isoformat(), logged_at.astimezone(timezone.utc).isoformat()),
        )

    row, = client.get(URL, headers=ADMIN).json()["preferences"]
    assert row["weekly_visits"] == 3 and row["special_event"] == "frequent_week"
    assert "최근 7일 동안 3일 방문" in row["care_reason"]
