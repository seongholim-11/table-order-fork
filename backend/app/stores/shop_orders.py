"""주문 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 주문 스키마를 바꾸면 통계(B 담당)도 확인한다.

Supabase 에서는 orders(주문) / order_items(줄) / order_item_components(AI 조합 구성 메뉴) 세 테이블로 나뉜다.
밖으로는 예전처럼 ts·lines 를 가진 주문 하나로 돌려준다.

[뼈대] 시그니처와 스키마만 남겼다. 구현은 TODO 를 따라 채운다.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, table_no INTEGER NOT NULL, member_id INTEGER, total INTEGER NOT NULL,
    roulette_discount_percent INTEGER NOT NULL DEFAULT 0, ai_combo INTEGER NOT NULL DEFAULT 0,
    recommendation_event_id INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL, menu_id TEXT, kind TEXT NOT NULL DEFAULT 'menu',
    name TEXT NOT NULL, option_label TEXT NOT NULL DEFAULT '', unit_price INTEGER NOT NULL, original_unit_price INTEGER,
    qty INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS order_item_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT, order_item_id INTEGER NOT NULL, menu_id TEXT, name TEXT NOT NULL,
    option_label TEXT NOT NULL DEFAULT '', qty INTEGER NOT NULL);
"""


class OrderMixin:
    def add_order(self, table_no: int, lines: list[dict], total: int, member_id: int | None) -> dict:
        """주문을 저장하고 order() 모양({id, table_no, member_id, total, ai_combo, ts, lines, ...})을 돌려준다.

        TODO: orders INSERT (줄 id 가 'combo:' 로 시작하는 줄이 있으면 ai_combo=True).
        TODO: 줄마다 order_items INSERT (combo 줄은 menu_id=null, kind='combo'), components 는 order_item_components 에 저장.
        TODO: menus 에 있는 id 만 menu_id 로 연결 (없으면 null)."""
        raise NotImplementedError

    def order(self, order_id: int) -> dict:
        """TODO: 주문 한 건 + 줄(lines, 조합 구성 components) 조회. created_at 은 ts 로 내보낸다."""
        raise NotImplementedError

    def orders(self, member_id: int | None = None) -> list[dict]:
        """TODO: 최신순 주문 목록. member_id 가 있으면 그 회원 것만."""
        raise NotImplementedError
