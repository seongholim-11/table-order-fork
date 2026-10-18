"""주문 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 주문 스키마를 바꾸면 통계(B 담당)도 확인한다.

Supabase 에서는 orders(주문) / order_items(줄) / order_item_components(AI 조합 구성 메뉴) 세 테이블로 나뉜다.
밖으로는 예전처럼 ts·lines 를 가진 주문 하나로 돌려준다.

[뼈대] 시그니처와 스키마만 남겼다. 구현은 TODO 를 따라 채운다.
"""
from datetime import datetime, timezone
SCHEMA = """\
CREATE TABLE IF NOT EXISTS orders (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no                   INTEGER NOT NULL,
    member_id                  INTEGER,
    total                      INTEGER NOT NULL,
    roulette_discount_percent  INTEGER NOT NULL DEFAULT 0,
    ai_combo                   INTEGER NOT NULL DEFAULT 0,
    recommendation_event_id    INTEGER,
    created_at                 TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            INTEGER NOT NULL,
    menu_id             TEXT,
    kind                TEXT NOT NULL DEFAULT 'menu',
    name                TEXT NOT NULL,
    option_label        TEXT NOT NULL DEFAULT '',
    unit_price          INTEGER NOT NULL,
    original_unit_price INTEGER,
    qty                 INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS order_item_components (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_item_id INTEGER NOT NULL,
    menu_id       TEXT,
    name          TEXT NOT NULL,
    option_label  TEXT NOT NULL DEFAULT '',
    qty           INTEGER NOT NULL
);
"""


class OrderMixin:
    def add_order(self, table_no: int, lines: list[dict], total: int, member_id: int | None) -> dict:
        """주문을 저장하고 order() 모양({id, table_no, member_id, total, ai_combo, ts, lines, ...})을 돌려준다.

        메뉴가 아직 seed되지 않은 개발 환경도 주문할 수 있도록, 실제 menus에 있는 id만 연결한다.
        주문과 주문 줄·조합 구성은 한 트랜잭션에서 저장해 중간 실패 시 일부 주문이 남지 않게 한다."""
        menu_ids = {line["id"] for line in lines if not line["id"].startswith("combo:")}
        menu_ids.update(component.get("id") for line in lines for component in (line.get("components") or [])
                        if component.get("id"))
        known_menu_ids = set()
        if menu_ids:
            placeholders = ", ".join("?" for _ in menu_ids)
            known_menu_ids = {row["id"] for row in self.db.all(
                f"SELECT id FROM menus WHERE id IN ({placeholders})", tuple(menu_ids))}

        ai_combo = any(line["id"].startswith("combo:") for line in lines)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.db.transaction():
            order_id = self._insert_id(
                "INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?,?,?,?,?)",
                (table_no, member_id, total, ai_combo, created_at))
            for line in lines:
                is_combo = line["id"].startswith("combo:")
                item_id = self._insert_id(
                    "INSERT INTO order_items (order_id, menu_id, kind, name, option_label, unit_price, original_unit_price, qty) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (order_id, None if is_combo else (line["id"] if line["id"] in known_menu_ids else None),
                     "combo" if is_combo else "menu", line["name"], line.get("opt", ""), line["unit"],
                     line.get("original_unit"), line["qty"]))
                for component in line.get("components") or []:
                    component_id = component.get("id")
                    component_menu_id = component_id if component_id in known_menu_ids else None
                    self._insert_id(
                        "INSERT INTO order_item_components (order_item_id, menu_id, name, option_label, qty) "
                        "VALUES (?,?,?,?,?)",
                        (item_id, component_menu_id, component["name"], component.get("opt", ""), component.get("qty", 1)))
        return self.order(order_id)

    def order(self, order_id: int) -> dict:
        """주문 한 건과 주문 줄·조합 구성을 화면용 모양으로 조립한다."""
        row = self.db.one(
            "SELECT o.id, o.table_no, o.member_id, o.total, o.roulette_discount_percent, o.ai_combo, "
            "o.recommendation_event_id, o.created_at AS ts, m.nickname "
            "FROM orders o LEFT JOIN members m ON m.id=o.member_id WHERE o.id=?", (order_id,))
        if not row:
            return None
        return self._with_lines(row)

    def orders(self, member_id: int | None = None) -> list[dict]:
        """최신 주문부터 읽는다. member_id가 주어지면 그 회원 주문만 조회한다."""
        where = ""
        params = ()
        if member_id is not None:
            where = " WHERE o.member_id=?"
            params = (member_id,)
        rows = self.db.all(
            "SELECT o.id, o.table_no, o.member_id, o.total, o.roulette_discount_percent, o.ai_combo, "
            "o.recommendation_event_id, o.created_at AS ts, m.nickname "
            f"FROM orders o LEFT JOIN members m ON m.id=o.member_id{where} "
            "ORDER BY o.created_at DESC, o.id DESC", params)
        return [self._with_lines(row) for row in rows]

    def table_orders(self, table_no: int, since: str | None) -> list[dict]:
        """기준 로그인 시각 이후 해당 테이블의 주문만 최신순으로 읽는다."""
        if since is None:
            return []
        rows = self.db.all(
            "SELECT o.id, o.table_no, o.member_id, o.total, o.roulette_discount_percent, o.ai_combo, "
            "o.recommendation_event_id, o.created_at AS ts, m.nickname "
            "FROM orders o LEFT JOIN members m ON m.id=o.member_id "
            "WHERE o.table_no=? AND o.created_at>=? ORDER BY o.created_at DESC, o.id DESC",
            (table_no, since))
        return [self._with_lines(row) for row in rows]

    def _insert_id(self, sql: str, params: tuple) -> int:
        """현재 트랜잭션 안에서 INSERT한 행의 id를 SQLite·Postgres 공통으로 가져온다."""
        cursor = self.db._execute(sql + (" RETURNING id" if self.db.pg else ""), params)
        if self.db.pg:
            return cursor.fetchone()["id"]
        return cursor.lastrowid

    def _with_lines(self, row: dict) -> dict:
        items = self.db.all(
            "SELECT id, menu_id, kind, name, option_label, unit_price, original_unit_price, qty "
            "FROM order_items WHERE order_id=? ORDER BY id", (row["id"],))
        lines = []
        for item in items:
            is_combo = item["kind"] == "combo"
            line = {"id": f"combo:{item['id']}" if is_combo else (item["menu_id"] or f"item:{item['id']}"),
                    "name": item["name"], "opt": item["option_label"], "unit": item["unit_price"], "qty": item["qty"]}
            if item["original_unit_price"] is not None:
                line["original_unit"] = item["original_unit_price"]
            if is_combo:
                components = self.db.all(
                    "SELECT id, menu_id, name, option_label, qty FROM order_item_components "
                    "WHERE order_item_id=? ORDER BY id", (item["id"],))
                line["components"] = [
                    {"id": c["menu_id"] or f"component:{c['id']}", "name": c["name"],
                     "opt": c["option_label"], "qty": c["qty"]} for c in components]
            lines.append(line)
        return {**row, "ai_combo": bool(row["ai_combo"]), "lines": lines}
