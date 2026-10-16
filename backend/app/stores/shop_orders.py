"""주문 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 주문 스키마를 바꾸면 통계(B 담당)도 확인한다.

Supabase 에서는 orders(주문) / order_items(줄) / order_item_components(AI 조합 구성 메뉴) 세 테이블로 나뉜다.
밖으로는 예전처럼 ts·lines 를 가진 주문 하나로 돌려준다.
"""

from app.stores.members import now_iso

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
    def _menu_id(self, value) -> str | None:
        """menus 에 있는 id 만 연결한다 (조합 줄 'combo:...' 나 지워진 메뉴는 null)."""
        return value if value and self.db.one("SELECT 1 FROM menus WHERE id=?", (value,)) else None

    def add_order(self, table_no: int, lines: list[dict], total: int, member_id: int | None) -> dict:
        ai = any(str(l.get("id", "")).startswith("combo:") for l in lines)
        oid = self.db.run("INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (?,?,?,?,?)",
                          (table_no, member_id, total, ai, now_iso()))
        for l in lines:
            combo = str(l.get("id", "")).startswith("combo:")
            item_id = self.db.run(
                "INSERT INTO order_items (order_id, menu_id, kind, name, option_label, unit_price, original_unit_price, qty) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (oid, None if combo else self._menu_id(l.get("id")), "combo" if combo else "menu", l["name"],
                 l.get("opt", ""), l["unit"], l.get("original_unit"), l["qty"]))
            for c in l.get("components") or []:
                self.db.run("INSERT INTO order_item_components (order_item_id, menu_id, name, option_label, qty) VALUES (?,?,?,?,?)",
                            (item_id, self._menu_id(c.get("id")), c["name"], c.get("opt", ""), c["qty"]))
        return self.order(oid)

    def _order(self, r: dict) -> dict:
        r["ts"], r["ai_combo"], r["lines"] = r.pop("created_at"), bool(r["ai_combo"]), []
        for it in self.db.all("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (r["id"],)):
            line = {"id": it["menu_id"] or "", "name": it["name"], "opt": it["option_label"], "unit": it["unit_price"],
                    "qty": it["qty"]}
            if it["original_unit_price"] is not None:
                line["original_unit"] = it["original_unit_price"]
            comps = self.db.all("SELECT menu_id, name, option_label, qty FROM order_item_components "
                                "WHERE order_item_id=? ORDER BY id", (it["id"],))
            if comps:
                line["components"] = [{"id": c["menu_id"] or "", "name": c["name"], "opt": c["option_label"], "qty": c["qty"]}
                                      for c in comps]
            r["lines"].append(line)
        return r

    def order(self, order_id: int) -> dict:
        return self._order(self.db.one("SELECT * FROM orders WHERE id=?", (order_id,)))

    def orders(self, member_id: int | None = None) -> list[dict]:
        if member_id is None:
            rows = self.db.all("SELECT * FROM orders ORDER BY id DESC")
        else:
            rows = self.db.all("SELECT * FROM orders WHERE member_id=? ORDER BY id DESC", (member_id,))
        return [self._order(r) for r in rows]
