"""사용자가 요청한 단골 선호도 예시 3명을 기존 데이터와 구분해 준비한다."""

from datetime import date, datetime, time, timedelta, timezone

from app.services.grades import KST
from app.stores.db import Database


# 고유한 로그인 식별값과 [예시] 이름으로 실제 손님 기록을 덮어쓰지 않는다.
EXAMPLES = (
    ("demo-regular-preference-v1-fish", "[예시] 먹태 단골", "a1", 8, "a2"),
    ("demo-regular-preference-v1-egg", "[예시] 계란말이 단골", "a4", 8, "a8"),
    ("demo-regular-preference-v1-pancake", "[예시] 파전 단골", "a8", 8, "a1"),
)


def _restore_example_records(db: Database) -> dict:
    """이번 기능이 만든 예시만 확인해 제거한다. 호출한 트랜잭션 안에서만 실행한다."""
    member_ids = []
    for key, nickname, *_ in EXAMPLES:
        found = db._execute("SELECT * FROM members WHERE kakao_id=?", (key,)).fetchone()
        if found is None:
            continue
        member = dict(found)
        if (member["nickname"] != nickname or member["visit_count"] != 11 or member["phone"]
                or member["marketing_consent"] or member.get("auth_user_id")):
            raise ValueError("예시 회원이 다른 용도로 변경되어 복원을 중단합니다.")
        member_id = member["id"]
        orders = db._execute("SELECT id, total FROM orders WHERE member_id=?", (member_id,)).fetchall()
        lines = db._execute(
            "SELECT i.order_id, i.menu_id, i.qty, i.unit_price, i.kind FROM order_items i "
            "JOIN orders o ON o.id=i.order_id WHERE o.member_id=?", (member_id,)).fetchall()
        totals = {row["id"]: row["total"] for row in orders}
        if (len(orders) != 11 or len(lines) != 11 or len({line["order_id"] for line in lines}) != 11
                or any(line["menu_id"] not in ("a1", "a2", "a4", "a8") or line["qty"] != 1
                       or line["kind"] != "menu" or line["unit_price"] != totals[line["order_id"]] for line in lines)):
            raise ValueError("예시 주문에 다른 기록이 추가되어 복원을 중단합니다.")
        # 실제 로그인·쿠폰·문자 등과 연결되었다면 다른 기능의 기록을 지우지 않는다.
        tables = ["table_logins", "recommendation_events"]
        if db.pg:
            tables += ["login_sessions", "sms_log_recipients", "alerts"]
        for table in tables:
            if db._execute(f"SELECT COUNT(*) AS n FROM {table} WHERE member_id=?", (member_id,)).fetchone()["n"]:
                raise ValueError("다른 기능과 연결된 예시이므로 복원을 중단합니다.")
        if db._execute(
                "SELECT COUNT(*) AS n FROM coupons WHERE member_id=? OR used_order_id IN "
                "(SELECT id FROM orders WHERE member_id=?)", (member_id, member_id)).fetchone()["n"]:
            raise ValueError("쿠폰과 연결된 예시이므로 복원을 중단합니다.")
        member_ids.append(member_id)
    # 모든 대상을 먼저 검사한 뒤, 그 회원의 예시 주문과 회원만 지운다.
    for member_id in member_ids:
        db._execute("DELETE FROM order_item_components WHERE order_item_id IN "
                    "(SELECT i.id FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.member_id=?)", (member_id,))
        db._execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE member_id=?)", (member_id,))
        db._execute("DELETE FROM orders WHERE member_id=?", (member_id,))
        db._execute("DELETE FROM members WHERE id=?", (member_id,))
    return {"restored_members": len(member_ids), "restored_orders": len(member_ids) * 11}


def seed_regular_examples(db: Database, today: date, *, reset_examples: bool = False) -> dict:
    """예시만 복원·추가할 수 있으며, 실패하면 복원 전 상태까지 함께 되돌린다."""
    restored = {}
    with db._lock:
        # run()의 건별 커밋을 피하고 전체 예시 생성에 성공했을 때만 저장한다.
        transaction = db._conn.transaction() if db.pg else db._conn
        with transaction:
            menus = {row["id"]: dict(row) for row in db._execute(
                "SELECT id, name, price FROM menus WHERE id IN ('a1', 'a2', 'a4', 'a8')").fetchall()}
            if len(menus) != 4:
                raise ValueError("예시에 필요한 메뉴 a1·a2·a4·a8이 모두 있어야 합니다.")
            store = db._execute("SELECT tables FROM store_info WHERE id=1").fetchone()
            if not store or store["tables"] < 1:
                raise ValueError("매장의 테이블 수를 먼저 설정해 주세요.")
            if reset_examples:
                restored = _restore_example_records(db)
            created_members, created_orders = 0, 0
            for index, (key, nickname, favorite, frequency, current) in enumerate(EXAMPLES):
                member = db._execute("SELECT id, nickname FROM members WHERE kakao_id=?", (key,)).fetchone()
                if member:
                    # 예전 실행 결과는 그대로 두고, 충돌·불완전한 자료를 임의로 덮어쓰지 않는다.
                    count = db._execute("SELECT COUNT(*) AS n FROM orders WHERE member_id=?", (member["id"],)).fetchone()["n"]
                    if member["nickname"] != nickname or count != 11:
                        raise ValueError("예시 식별값과 기존 기록이 일치하지 않아 생성을 중단합니다.")
                    continue
                at = datetime.combine(today, time(12), tzinfo=KST)
                stamp = at.astimezone(timezone.utc).isoformat()
                created = (at - timedelta(days=10)).astimezone(timezone.utc).isoformat()
                member_id = db._execute(
                    "INSERT INTO members (kakao_id, nickname, visit_count, last_visit_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?) RETURNING id", (key, nickname, 11, stamp, created)).fetchone()["id"]
                created_members += 1
                for day in range(11):
                    # 모두 같은 80% 기준을 충족하고, 오늘은 평소와 다른 안주를 주문한 상황으로 준비한다.
                    menu_id = current if day == 0 else favorite if day <= frequency else "a1" if favorite != "a1" else "a4"
                    menu = menus[menu_id]
                    order_at = (at - timedelta(days=day)).astimezone(timezone.utc).isoformat()
                    table_no = index % store["tables"] + 1
                    order_id = db._execute(
                        "INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                        (table_no, member_id, menu["price"], order_at)).fetchone()["id"]
                    db._execute(
                        "INSERT INTO order_items (order_id, menu_id, name, qty, unit_price, kind) VALUES (?, ?, ?, ?, ?, ?)",
                        (order_id, menu_id, menu["name"], 1, menu["price"], "menu"))
                    created_orders += 1
    return {**restored, "created_members": created_members, "created_orders": created_orders}


def remove_regular_examples(db: Database) -> dict:
    """식별값·주문 내역이 그대로인 예시 3명만 연결된 예시 주문과 함께 제거한다."""
    with db._lock:
        # 기존의 대상 검사를 재사용하고, 제거 중 실패해도 일부만 삭제되지 않게 한다.
        transaction = db._conn.transaction() if db.pg else db._conn
        with transaction:
            return _restore_example_records(db)
