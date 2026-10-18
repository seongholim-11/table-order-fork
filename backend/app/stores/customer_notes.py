"""마케팅 AI 추천의 단골 선호도 분석에 필요한 주문 이력을 읽는다."""

from app.stores.db import Database


class CustomerNotesStore:
    def __init__(self, db: Database):
        self.db = db

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
