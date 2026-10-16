"""메뉴 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다)."""

import json
from pathlib import Path

from app.stores.db import Database

SEED = Path(__file__).resolve().parent.parent / "seed" / "menu.json"
MENU_FIELDS = ("name", "cat", "price", "desc", "image_url", "soldout", "spicy", "weight", "set_ok", "emoji", "tags")

# 컬럼 이름은 Supabase 스키마(db/fbgrowth_schema.sql)를 따른다. 밖으로는 예전 키(cat, desc, soldout)로 내보낸다.
SCHEMA = """
CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY, category_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '🍽️', tags TEXT NOT NULL DEFAULT '[]',
    is_soldout INTEGER NOT NULL DEFAULT 0, spicy INTEGER NOT NULL DEFAULT 0, weight INTEGER NOT NULL DEFAULT 50,
    set_ok INTEGER NOT NULL DEFAULT 0, image_url TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
"""

SELECT = ('SELECT id, category_id AS cat, name, description AS "desc", price, emoji, tags, is_soldout AS soldout, '
          'spicy, weight, set_ok, image_url FROM menus')


def _menu(row: dict) -> dict:
    row["tags"] = Database.from_list(row["tags"])
    for k in ("soldout", "set_ok"):
        row[k] = bool(row[k])
    return row


class MenuMixin:
    def seed_menus(self) -> None:
        """메뉴 테이블이 비어 있을 때만 seed/menu.json 을 넣는다."""
        if not self.db.one("SELECT 1 FROM menus LIMIT 1"):
            for i, m in enumerate(json.loads(SEED.read_text(encoding="utf-8"))):
                self.save_menu(m["id"], m, sort=i)

    # ---- 메뉴
    def menus(self) -> list[dict]:
        return [_menu(r) for r in self.db.all(SELECT + " ORDER BY sort_order, id")]

    def menu(self, menu_id: str) -> dict | None:
        r = self.db.one(SELECT + " WHERE id=?", (menu_id,))
        return _menu(r) if r else None

    def save_menu(self, menu_id: str, fields: dict, sort: int | None = None) -> dict:
        """있으면 주어진 필드만 수정, 없으면 새로 만든다."""
        cur = self.menu(menu_id)
        data = {**(cur or {"desc": "", "emoji": "🍽️", "tags": [], "soldout": False, "spicy": 0, "weight": 50,
                           "set_ok": False, "image_url": ""}), **{k: v for k, v in fields.items() if k in MENU_FIELDS}}
        if sort is None:
            row = self.db.one("SELECT sort_order FROM menus WHERE id=?", (menu_id,))
            sort = row["sort_order"] if row else self.db.one("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM menus")["n"]
        self.db.run(
            """INSERT INTO menus (id, category_id, name, description, price, emoji, tags, is_soldout, spicy, weight, set_ok,
                                  image_url, sort_order)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET category_id=excluded.category_id, name=excluded.name,
                 description=excluded.description, price=excluded.price, emoji=excluded.emoji, tags=excluded.tags,
                 is_soldout=excluded.is_soldout, spicy=excluded.spicy, weight=excluded.weight, set_ok=excluded.set_ok,
                 image_url=excluded.image_url""",
            (menu_id, data["cat"], data["name"], data["desc"], data["price"], data["emoji"],
             self.db.to_list(data["tags"]), bool(data["soldout"]), data["spicy"], data["weight"],
             bool(data["set_ok"]), data["image_url"], sort))
        return self.menu(menu_id)

    def delete_menu(self, menu_id: str) -> bool:
        existed = self.menu(menu_id) is not None
        self.db.run("DELETE FROM menus WHERE id=?", (menu_id,))
        return existed
