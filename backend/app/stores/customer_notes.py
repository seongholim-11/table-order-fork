"""마케팅 AI 추천의 단골 선호도 분석에 필요한 주문 이력을 읽는다."""

from app.stores.db import Database


# 응대 제안 카드를 사장님이 '확인'한 기록. (손님, 주문) 한 쌍이 한 카드이므로 둘을 합쳐 기본키로 쓴다.
SCHEMA = """\
CREATE TABLE IF NOT EXISTS service_tip_checks (
    member_id  INTEGER NOT NULL,
    order_id   INTEGER NOT NULL,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (member_id, order_id)
);
"""


class CustomerNotesStore:
    def __init__(self, db: Database):
        self.db = db
        self.db.script(SCHEMA)  # 표가 없으면 만든다(있으면 그대로 둔다)

    def checked_tips(self) -> set[tuple[int, int]]:
        """확인 처리된 응대 제안을 (member_id, order_id) 묶음으로 돌려준다."""
        rows = self.db.all("SELECT member_id, order_id FROM service_tip_checks")
        return {(row["member_id"], row["order_id"]) for row in rows}

    def set_tip_checked(self, member_id: int, order_id: int, checked: bool) -> None:
        """확인 기록을 남기거나(checked=True) 지운다(False). 이미 있어도 오류 없이 넘어간다."""
        if checked:
            self.db.run("INSERT INTO service_tip_checks (member_id, order_id) VALUES (?, ?) "
                        "ON CONFLICT (member_id, order_id) DO NOTHING", (member_id, order_id))
        else:
            self.db.run("DELETE FROM service_tip_checks WHERE member_id=? AND order_id=?", (member_id, order_id))

    def orders(self, minimum_visits: int = 2) -> list[dict]:
        """두 번째 이상 방문한 회원의 과거·오늘 주문을 가져온다."""
        return self.db.all(
            "SELECT o.id, o.member_id, o.table_no, o.created_at AS ts "
            "FROM orders o JOIN members m ON m.id=o.member_id "
            "WHERE m.visit_count>=? ORDER BY o.id", (minimum_visits,))

    def lines(self, minimum_visits: int = 2) -> list[dict]:
        """유료 메뉴와 AI 조합 구성 메뉴를 읽고, 룰렛 서비스 메뉴는 제외한다."""
        # 한 번에 여러 개 주문해도 선호도를 부풀리지 않도록 서비스에서 주문일별로 한 번만 센다.
        return self.db.all(
            "SELECT i.order_id, i.menu_id, i.name, i.qty FROM order_items i "
            "JOIN orders o ON o.id=i.order_id JOIN members m ON m.id=o.member_id "
            "WHERE m.visit_count>=? AND i.kind='menu' UNION ALL "
            "SELECT i.order_id, c.menu_id, c.name, c.qty*i.qty AS qty FROM order_item_components c "
            "JOIN order_items i ON i.id=c.order_item_id JOIN orders o ON o.id=i.order_id "
            "JOIN members m ON m.id=o.member_id WHERE m.visit_count>=? AND i.kind='combo'",
            (minimum_visits, minimum_visits))

    def visits(self, minimum_visits: int = 2) -> list[dict]:
        """방문 빈도는 주문 건수가 아니라 제품 규칙대로 로그인 날짜를 기준으로 읽는다."""
        return self.db.all(
            "SELECT t.member_id, t.table_no, t.login_day, t.logged_in_at "
            "FROM table_logins t JOIN members m ON m.id=t.member_id "
            "WHERE m.visit_count>=? ORDER BY t.logged_in_at, t.id", (minimum_visits,))

    def menus(self) -> list[dict]:
        """현재 메뉴 ID·분류·품절 여부를 근거로 안주를 구분한다."""
        return self.db.all("SELECT id, name, category_id, is_soldout FROM menus ORDER BY id")

    def activity(self, limit: int = 5) -> dict:
        """폴링용: 가장 최근 로그인·주문 번호와 최근 사건 몇 건을 읽는다. 번호가 바뀌면 새 로그인/주문이 생긴 것이다."""
        login = self.db.one("SELECT COALESCE(MAX(id), 0) AS last FROM table_logins")["last"]
        order = self.db.one("SELECT COALESCE(MAX(id), 0) AS last FROM orders")["last"]
        logins = self.db.all(
            "SELECT 'login' AS kind, l.id, l.table_no, m.nickname, l.logged_in_at AS at "
            "FROM table_logins l JOIN members m ON m.id=l.member_id ORDER BY l.id DESC LIMIT ?", (limit,))
        orders = self.db.all(
            "SELECT 'order' AS kind, o.id, o.table_no, m.nickname, o.created_at AS at "
            "FROM orders o LEFT JOIN members m ON m.id=o.member_id ORDER BY o.id DESC LIMIT ?", (limit,))
        return {"login_id": login, "order_id": order, "recent": logins + orders}
