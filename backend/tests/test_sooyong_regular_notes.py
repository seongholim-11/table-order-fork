"""수용: 30일 경계와 실제 주문 근거가 있는 단골 멘트만 반환하는지 확인한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.settings import Settings
from app.services.grades import KST, grade_of
from tests.conftest import ADMIN


@pytest.fixture(autouse=True)
def _empty_menus(client):
    """서버가 처음 뜰 때 기본 메뉴가 들어가므로, 빈 DB를 전제로 한 이 파일의 테스트를 위해 메뉴를 비운다."""
    client.app.state.db.run("DELETE FROM menus")


URL = "/admin/api/marketing/regular-preferences"


def add_order(client, member_id, day, menu_id, name, *, qty=1, kind="menu", table=7):
    """실제 고객 기록 대신 테스트 메모리 DB에만 주문을 준비한다."""
    db = client.app.state.db
    at = datetime.now(KST).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=day)
    order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                   (table, member_id, 14000, at.astimezone(timezone.utc).isoformat()))
    line = db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, kind) VALUES (?, ?, ?, ?, ?, ?)",
                  (order, menu_id, name, qty, 14000, kind))
    return order, line


def prepare(client, *, days=5, favorites=4, visits=5, current=True):
    db = client.app.state.db
    for menu_id, name, category in (("note-fish", "먹태구이", "anju"), ("note-egg", "계란말이", "anju"),
                                     ("note-beer", "생맥주", "beer")):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
               (menu_id, category, name, 14000))
    member = client.app.state.members.upsert_login("note-regular", "메모 단골")
    db.run("UPDATE members SET visit_count=? WHERE id=?", (visits, member["id"]))
    for day in range(1, days + 1):
        favorite = day <= favorites
        add_order(client, member["id"], day, "note-fish" if favorite else "note-egg",
                  "먹태구이" if favorite else "계란말이")
    if current:
        add_order(client, member["id"], 0, "note-egg", "계란말이")
    return member


def notes(client):
    response = client.get(URL, headers=ADMIN)
    assert response.status_code == 200
    return response.json()["preferences"]


def test_thirty_day_boundary_uses_kst_and_keeps_internal_grade_contract():
    today = datetime(2026, 10, 17, 12, tzinfo=KST).date()
    assert Settings(_env_file=None).grade_dormant_days == 30
    # UTC로는 같은 날짜여도 KST 0시를 넘으면 29일/30일 판정이 달라진다.
    assert grade_of({"visit_count": 5, "last_visit_at": "2026-09-17T14:59:59+00:00"}, today) == "휴면"
    assert grade_of({"visit_count": 5, "last_visit_at": "2026-09-17T15:00:00+00:00"}, today) == "단골"


def test_eighty_percent_history_and_different_today_create_note_without_writing(client):
    member = prepare(client)
    before = client.app.state.members.all()
    row, = notes(client)
    assert row["member_id"] == member["id"] and row["visit_count"] == 5
    assert row["history_days"] == 5 and row["favorite_days"] == 4 and row["preference_rate"] == .8
    assert row["favorite_menu"] == "먹태구이" and row["changed_today"] and row["today_table"] == 7
    assert row["delivery_menu"] == "계란말이"
    assert "5번째 방문" in row["context"] and "오늘 주문: 계란말이" in row["context"]
    assert "5일 중 4일에 먹태구이" in row["context"] and "오늘 확인된 주문에는 먹태구이 메뉴가 없습니다" in row["context"]
    assert row["note"] and "왜" not in row["note"]
    assert client.app.state.members.all() == before


@pytest.mark.parametrize("kwargs", [{"days": 4}, {"favorites": 3}, {"days": 0}, {"visits": 4}])
def test_regular_without_preference_gets_visit_notice_but_nonregular_does_not(client, kwargs):
    prepare(client, **kwargs)
    rows = notes(client)
    if kwargs.get("visits") == 4:
        assert rows == []
    else:
        row, = rows
        assert row["visit_count"] == 5 and "5번째 방문" in row["context"]
        assert row["favorite_menu"] is None and row["preference_rate"] is None
        assert row["changed_today"] is None and "80%" not in row["context"]
        assert "먹태" not in row["note"]


def test_multiple_orders_and_quantity_do_not_inflate_daily_frequency(client):
    member = prepare(client, favorites=3)
    for _ in range(8):
        add_order(client, member["id"], 1, "note-fish", "먹태구이", qty=20)
    row, = notes(client)
    assert row["favorite_menu"] is None and row["preference_rate"] is None
    assert row["visit_count"] == 5


def test_new_today_order_is_reflected_and_other_tables_are_included(client):
    member = prepare(client)
    assert notes(client)[0]["changed_today"]
    add_order(client, member["id"], 0, "note-fish", "먹태구이", table=12)
    row, = notes(client)
    assert not row["changed_today"] and "오늘도 먹태구이 주문이 확인" in row["context"]
    assert row["today_table"] == 12 and row["delivery_menu"] == "먹태구이"


def test_no_today_order_is_hidden_but_paid_drink_also_identifies_regular(client):
    member = prepare(client, current=False)
    assert notes(client) == []
    add_order(client, member["id"], 0, "note-beer", "생맥주")
    row, = notes(client)
    assert row["delivery_menu"] == "생맥주" and "오늘 주문: 생맥주" in row["context"]
    assert row["favorite_menu"] == "먹태구이" and "다른 안주" not in row["context"]


def test_combo_components_count_and_free_items_do_not_count(client):
    member = prepare(client, favorites=3)
    _, combo = add_order(client, member["id"], 4, None, "AI 조합", kind="combo", qty=2)
    client.app.state.db.run("INSERT INTO order_item_components (order_item_id, menu_id, name, qty) VALUES (?, ?, ?, ?)",
                            (combo, "note-fish", "먹태구이", 3))
    assert notes(client)[0]["preference_rate"] == .8
    add_order(client, member["id"], 0, "note-fish", "먹태구이", kind="roulette_service")
    assert notes(client)[0]["changed_today"]


def test_beer_preference_and_other_members_orders_are_not_customer_snack_evidence(client):
    member = prepare(client, favorites=3)
    other = client.app.state.members.upsert_login("note-other", "다른 고객")
    for day in range(1, 6):
        add_order(client, member["id"], day, "note-beer", "생맥주", qty=10)
        add_order(client, other["id"], day, "note-fish", "먹태구이")
        add_order(client, None, day, "note-fish", "먹태구이")
    row, = notes(client)
    assert row["favorite_menu"] is None and row["preference_rate"] is None


def test_renamed_menu_keeps_identity_and_soldout_note_does_not_ask_why(client):
    prepare(client)
    client.app.state.db.run("UPDATE menus SET name=?, is_soldout=? WHERE id=?", ("먹태 새 이름", True, "note-fish"))
    row, = notes(client)
    assert row["favorite_menu"] == "먹태 새 이름" and "현재 품절" in row["context"]
    assert "품절이라" not in row["note"] and "왜" not in row["note"]


def test_empty_database_and_auth_before_reading_orders(client, monkeypatch):
    assert notes(client) == []
    from app.stores.customer_notes import CustomerNotesStore

    def unexpected_read(self):
        pytest.fail("인증 없는 요청이 고객 주문 이력을 조회했습니다.")

    monkeypatch.setattr(CustomerNotesStore, "orders", unexpected_read)
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_dormant_regular_is_not_reported_as_current_regular(client):
    member = prepare(client)
    client.app.state.db.run("UPDATE members SET last_visit_at=? WHERE id=?",
                            ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(), member["id"]))
    assert notes(client) == []


def test_three_examples_have_real_rates_and_do_not_duplicate_orders(client):
    from app.services.grades import KST
    from app.stores.regular_examples import EXAMPLES, seed_regular_examples

    db = client.app.state.db
    for menu_id, name in (("a1", "먹태구이"), ("a2", "골뱅이"), ("a4", "계란말이"), ("a8", "해물파전")):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", name, 14000))
    today = datetime.now(KST).date()
    assert seed_regular_examples(db, today) == {"created_members": 3, "created_orders": 33}
    assert seed_regular_examples(db, today) == {"created_members": 0, "created_orders": 0}
    rows = {row["nickname"]: row for row in notes(client)}
    assert len(rows) == 3
    for _, nickname, _, frequency, _ in EXAMPLES:
        assert rows[nickname]["preference_rate"] == frequency / 10
        assert rows[nickname]["history_days"] == 10
    assert all(not member["marketing_consent"] and not member["phone"] for member in client.app.state.members.all())


def test_example_creation_requires_existing_menus_and_is_atomic(client, monkeypatch):
    from app.stores.regular_examples import seed_regular_examples

    db = client.app.state.db
    with pytest.raises(ValueError):
        seed_regular_examples(db, datetime.now(KST).date())
    assert client.app.state.members.all() == []
    for menu_id in ("a1", "a2", "a4", "a8"):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, 14000))
    execute = db._execute

    def fail_after_member(sql, params=()):
        if sql.startswith("INSERT INTO orders"):
            raise RuntimeError("테스트용 주문 저장 실패")
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", fail_after_member)
    with pytest.raises(RuntimeError):
        seed_regular_examples(db, datetime.now(KST).date())
    assert client.app.state.members.all() == []


def test_example_reset_restores_only_examples_and_keeps_original_records(client):
    from app.stores.regular_examples import EXAMPLES, seed_regular_examples

    db = client.app.state.db
    for menu_id in ("a1", "a2", "a4", "a8"):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, 14000))
    original = client.app.state.members.upsert_login("original-customer", "기존 고객")
    order, _ = add_order(client, original["id"], 1, "a1", "기존 주문")
    before_order = db.one("SELECT * FROM orders WHERE id=?", (order,))
    today = datetime.now(KST).date()
    seed_regular_examples(db, today)
    result = seed_regular_examples(db, today, reset_examples=True)
    assert result == {"restored_members": 3, "restored_orders": 33, "created_members": 3, "created_orders": 33}
    assert client.app.state.members.get(original["id"]) == original
    assert db.one("SELECT * FROM orders WHERE id=?", (order,)) == before_order
    assert len(notes(client)) == 3
    assert {row["nickname"] for row in notes(client)} == {row[1] for row in EXAMPLES}


def test_example_reset_failure_rolls_back_deletions_too(client, monkeypatch):
    from app.stores.regular_examples import seed_regular_examples

    db = client.app.state.db
    for menu_id in ("a1", "a2", "a4", "a8"):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, 14000))
    today = datetime.now(KST).date()
    seed_regular_examples(db, today)
    before = client.app.state.members.all()
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    execute = db._execute

    def fail_after_restoring(sql, params=()):
        if sql.startswith("INSERT INTO orders"):
            raise RuntimeError("테스트용 재추가 실패")
        return execute(sql, params)

    monkeypatch.setattr(db, "_execute", fail_after_restoring)
    with pytest.raises(RuntimeError):
        seed_regular_examples(db, today, reset_examples=True)
    assert client.app.state.members.all() == before
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders


def test_modified_example_is_not_removed_by_reset(client):
    from app.stores.regular_examples import EXAMPLES, seed_regular_examples

    db = client.app.state.db
    for menu_id in ("a1", "a2", "a4", "a8"):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, 14000))
    today = datetime.now(KST).date()
    seed_regular_examples(db, today)
    db.run("UPDATE members SET phone=? WHERE kakao_id=?", ("010-0000-0000", EXAMPLES[0][0]))
    before = client.app.state.members.all()
    with pytest.raises(ValueError):
        seed_regular_examples(db, today, reset_examples=True)
    assert client.app.state.members.all() == before
    assert db.one("SELECT COUNT(*) AS n FROM orders")["n"] == 33


def test_serving_another_menu_does_not_deny_favorite_already_ordered_today(client):
    member = prepare(client)
    add_order(client, member["id"], 0, "note-fish", "먹태구이")
    add_order(client, member["id"], 0, "note-egg", "계란말이")
    row, = notes(client)
    assert row["delivery_menu"] == "계란말이"
    assert not row["changed_today"] and "오늘도 먹태구이 주문이 확인" in row["context"]
    assert row["today_menus"] == ["계란말이", "먹태구이"]
    assert "오늘 확인된 주문에는 먹태구이 메뉴가 없습니다" not in row["context"]
    assert "오늘은 다른 메뉴" not in row["note"]


def test_only_members_classified_as_regular_by_server_rules_are_used(client):
    from app.core.settings import get_settings

    member = prepare(client)
    config = Settings(_env_file=None, admin_token="admin-secret", grade_regular_visits=8)
    client.app.dependency_overrides[get_settings] = lambda: config
    assert notes(client) == []
    client.app.state.db.run("UPDATE members SET visit_count=8 WHERE id=?", (member["id"],))
    assert notes(client)[0]["member_id"] == member["id"]


def test_ten_ordering_regulars_are_all_reported_without_preference_or_limit(client):
    """선호 메뉴가 없는 단골 10명이 주문해도 모두 안내하고 주문 없는 회원은 제외한다."""
    db = client.app.state.db
    db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
           ("ten-menu", "anju", "오늘의 안주", 14000))
    expected = set()
    for index in range(11):
        member = client.app.state.members.upsert_login(f"ten-regular-{index}", f"단골 {index}")
        db.run("UPDATE members SET visit_count=? WHERE id=?", (5 + index, member["id"]))
        if index < 10:
            add_order(client, member["id"], 0, "ten-menu", "오늘의 안주", table=index + 1)
            expected.add(member["id"])
    rows = notes(client)
    assert len(rows) == 10 and {row["member_id"] for row in rows} == expected
    assert {row["today_table"] for row in rows} == set(range(1, 11))
    assert all(row["preference_rate"] is None and row["favorite_menu"] is None for row in rows)
    assert len({row["note"] for row in rows}) > 1


def test_visit_greetings_change_with_visit_situation_without_a_preference(client):
    member = prepare(client, days=0)
    greetings = set()
    for visits in (5, 8, 12):
        client.app.state.db.run("UPDATE members SET visit_count=? WHERE id=?", (visits, member["id"]))
        row, = notes(client)
        assert row["favorite_menu"] is None
        assert f"{visits}번째 방문" in row["visit_context"]
        assert "80%" not in row["visit_context"] + row["visit_note"]
        greetings.add(row["visit_note"])
    assert len(greetings) == 3


def test_varied_menu_and_long_gap_greetings_follow_order_records(client):
    member = prepare(client, days=0, visits=8)
    db = client.app.state.db
    db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)",
           ("note-pancake", "anju", "파전", 14000))
    for days, menu_id, name in ((1, "note-fish", "먹태구이"), (2, "note-egg", "계란말이"),
                                (3, "note-pancake", "파전")):
        add_order(client, member["id"], days, menu_id, name)
    varied, = notes(client)
    assert varied["favorite_menu"] is None and "여러 안주" in varied["visit_context"]
    assert "80%" not in varied["visit_context"] + varied["visit_note"]
    # 과거 주문만 14일 이상 이전으로 옮겨, 실제 주문 간격에 맞는 인사로 바뀌는지 확인한다.
    for order in db.all("SELECT id, created_at FROM orders ORDER BY id"):
        stamp = datetime.fromisoformat(order["created_at"])
        if stamp.astimezone(KST).date() < datetime.now(KST).date():
            db.run("UPDATE orders SET created_at=? WHERE id=?", ((stamp - timedelta(days=13)).isoformat(), order["id"]))
    returned, = notes(client)
    assert "이전 주문은 14일 전" in returned["visit_context"]
    assert returned["visit_note"] != varied["visit_note"]


def test_remove_examples_keeps_actual_customers_and_orders_and_is_repeatable(client):
    from app.stores.regular_examples import EXAMPLES, remove_regular_examples, seed_regular_examples

    db = client.app.state.db
    for menu_id in ("a1", "a2", "a4", "a8"):
        db.run("INSERT INTO menus (id, category_id, name, price) VALUES (?, ?, ?, ?)", (menu_id, "anju", menu_id, 14000))
    actual = client.app.state.members.upsert_login("actual-regular", "실제 단골")
    add_order(client, actual["id"], 0, "a1", "a1")
    before_members = client.app.state.members.all()
    before_orders = db.all("SELECT * FROM orders ORDER BY id")
    before_lines = db.all("SELECT * FROM order_items ORDER BY id")
    seed_regular_examples(db, datetime.now(KST).date())
    assert remove_regular_examples(db) == {"restored_members": 3, "restored_orders": 33}
    assert client.app.state.members.all() == before_members
    assert db.all("SELECT * FROM orders ORDER BY id") == before_orders
    assert db.all("SELECT * FROM order_items ORDER BY id") == before_lines
    assert not {example[0] for example in EXAMPLES} & {row["kakao_id"] for row in client.app.state.members.all()}
    assert remove_regular_examples(db) == {"restored_members": 0, "restored_orders": 0}
