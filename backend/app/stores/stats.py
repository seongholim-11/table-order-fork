"""수용 담당 통계 조회. 주문 저장 코드는 건드리지 않고 읽기만 한다."""

from datetime import date, datetime, time, timedelta, timezone

from app.services.grades import KST
from app.stores.db import Database


class StatsStore:
    def __init__(self, db: Database):
        self.db = db

    def sales_orders(self) -> list[dict]:
        """추가 통계는 주문 금액·시각만 필요하므로 메뉴 줄을 중복 조회하지 않는다."""
        return self.db.all(
            "SELECT o.id, o.table_no, o.member_id, o.total, o.ai_combo, o.created_at AS ts, m.nickname "
            "FROM orders o LEFT JOIN members m ON m.id=o.member_id ORDER BY o.id")

    def menu_stock(self) -> list[dict]:
        """메뉴 관리의 더미 응답 대신 현재 DB의 이름과 품절 상태를 읽는다."""
        return self.db.all("SELECT id, name, is_soldout FROM menus ORDER BY sort_order, id")

    def menu_sales(self) -> list[dict]:
        """일반 메뉴와 조합 구성 메뉴를 실제 판매 수량으로 합칠 자료를 읽는다."""
        # 조합 2세트에 같은 메뉴가 3개씩 있으면 6개 판매로 센다. 조합 줄 자체는 제외한다.
        return self.db.all(
            "SELECT i.menu_id, i.name, i.qty FROM order_items i JOIN orders o ON o.id=i.order_id "
            "WHERE i.kind <> 'combo' UNION ALL "
            "SELECT c.menu_id, c.name, c.qty*i.qty AS qty FROM order_item_components c "
            "JOIN order_items i ON i.id=c.order_item_id JOIN orders o ON o.id=i.order_id "
            "WHERE i.kind='combo'")

    def orders(self) -> list[dict]:
        """주문 저장 담당 파일을 수정하지 않고 통계에 필요한 기록을 묶어 읽는다."""
        orders = self.db.all("SELECT id, member_id, total, ai_combo, created_at AS ts FROM orders ORDER BY id")
        lines = self.db.all("SELECT id, order_id, kind, name, qty FROM order_items ORDER BY id")
        components = self.db.all("SELECT order_item_id, name, qty FROM order_item_components ORDER BY id")
        # 주문마다 쿼리하지 않도록 세 번의 조회 결과를 ID로 연결한다.
        by_order = {order["id"]: order for order in orders}
        by_line = {line["id"]: line for line in lines}
        for order in orders:
            order["lines"] = []
        for line in lines:
            line["components"] = []
            by_order[line["order_id"]]["lines"].append(line)
        for component in components:
            by_line[component["order_item_id"]]["components"].append(component)
        return orders

    def recommendation_count(self) -> int:
        """인기 메뉴와 같은 전체 기간의 추천 노출 횟수를 읽는다."""
        return int(self.db.one("SELECT COUNT(*) AS count FROM recommendation_events")["count"])

    def count_orders_on(self, day: date) -> int:
        """한국 시간의 지정 날짜에 생성된 주문 건수를 반환한다."""
        start = datetime.combine(day, time.min, tzinfo=KST).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        if self.db.pg:
            # Supabase의 timestamptz는 UTC 범위로 비교하며, 다음 날 0시는 제외한다.
            row = self.db.one("SELECT COUNT(*) AS count FROM orders WHERE created_at >= ? AND created_at < ?",
                              (start.isoformat(), end.isoformat()))
            return int(row["count"])

        # SQLite는 시각이 문자열이다. 공백·T·시간대 표기가 섞여도 날짜를 정확하게 비교한다.
        count = 0
        for row in self.db.all("SELECT created_at FROM orders"):
            created_at = datetime.fromisoformat(row["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)  # CURRENT_TIMESTAMP는 UTC다.
            if start <= created_at < end:
                count += 1
        return count
