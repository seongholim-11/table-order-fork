"""메뉴 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). [뼈대] 시그니처와 스키마만 남겼다."""

import json
from pathlib import Path

from app.stores.db import Database

MENU_FIELDS = ("name", "cat", "price", "desc", "image_url", "soldout", "spicy", "weight", "set_ok", "emoji", "tags")

# 컬럼 이름은 Supabase 스키마(db/fbgrowth_schema.sql)를 따른다. 밖으로는 예전 키(cat, desc, soldout)로 내보낸다.
SCHEMA = """\
CREATE TABLE IF NOT EXISTS menus (
    id          TEXT PRIMARY KEY,
    category_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,
    emoji       TEXT NOT NULL DEFAULT '🍽️',
    tags        TEXT NOT NULL DEFAULT '[]',
    is_soldout  INTEGER NOT NULL DEFAULT 0,
    spicy       INTEGER NOT NULL DEFAULT 0,
    weight      INTEGER NOT NULL DEFAULT 50,
    set_ok      INTEGER NOT NULL DEFAULT 0,
    image_url   TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0
);
"""

class MenuMixin:
    db:Database

    @staticmethod
    def _to_db_fields(fields: dict) -> dict:
        # API 필드명 세 개만 DB 컬럼명으로 바꾼다.
        names = {"cat": "category_id", "desc": "description", "soldout": "is_soldout"}
        return {names.get(key, key): value for key, value in fields.items()}

    @staticmethod
    def _from_db_fields(fields: dict) -> dict:
        # DB 컬럼명 세 개만 API 필드명으로 바꾼다.
        names = {"category_id": "cat", "description": "desc", "is_soldout": "soldout"}
        return {names.get(key, key): value for key, value in fields.items()}


    def seed_menus(self) -> None:
        """메뉴 테이블이 비어 있을 때만 seed/menu.json 을 넣는다.

        TODO: menus 가 비어 있으면 seed/menu.json 을 읽어 save_menu(id, menu, sort=순번) 로 넣는다."""
        if not self.menus():
            seed_path = Path(__file__).resolve().parent.parent / "seed" / "menu.json"
            with open(seed_path, mode="r", encoding="utf-8") as f:
                menus = json.load(f)

            for sort, menu in enumerate(menus):
                self.save_menu(menu_id=menu["id"],fields=menu,sort=sort)

    def menus(self) -> list[dict]:
        """TODO: 정렬(sort_order, id)된 전체 메뉴. 컬럼 category_id→cat, description→desc, is_soldout→soldout 로 이름을 바꿔
        내보내고 tags 는 db.from_list, soldout·set_ok 는 bool 로 만든다."""
        rows = self.db.all(
            "SELECT id, category_id, name, description, price, emoji, tags, is_soldout, "
            "spicy, weight, set_ok, image_url FROM menus ORDER BY sort_order, id"
        )
        menus = []
        for row in rows:
            # DB 컬럼명을 기존 API 필드명으로 바꾸고, 화면에서 쓰기 좋은 자료형으로 변환한다.
            menu = self._from_db_fields(row)
            menu["tags"] = self.db.from_list(menu["tags"])
            menu["soldout"] = bool(menu["soldout"])
            menu["set_ok"] = bool(menu["set_ok"])
            menus.append(menu)
        return menus

    def menu(self, menu_id: str) -> dict | None:
        """메뉴 ID로 한 건을 조회하고 API 필드 모양으로 돌려준다."""
        row = self.db.one(
            "SELECT id, category_id, name, description, price, emoji, tags, is_soldout, "
            "spicy, weight, set_ok, image_url FROM menus WHERE id=?",
            (menu_id,),
        )
        if row is None:
            return None

        # DB 컬럼명과 자료형을 손님·관리자 API가 쓰는 모양으로 바꾼다.
        menu = self._from_db_fields(row)
        menu["tags"] = self.db.from_list(menu["tags"])
        menu["soldout"] = bool(menu["soldout"])
        menu["set_ok"] = bool(menu["set_ok"])
        return menu

    def save_menu(self, menu_id: str, fields: dict, sort: int | None = None) -> dict:
        """있으면 주어진 필드(MENU_FIELDS)만 수정, 없으면 기본값을 채워 새로 만든다.

        TODO: INSERT ... ON CONFLICT(id) DO UPDATE. sort 가 없으면 기존 sort_order, 새 메뉴면 MAX(sort_order)+1.
        TODO: 저장한 메뉴를 menu() 로 읽어 반환."""

        # 새 메뉴에서 생략된 필드는 기본값으로 채운다.
        values = {
            "category_id": "side", "name": "새 메뉴", "price": 0,
            "description": "", "image_url": "", "is_soldout": False,
            "spicy": 0, "weight": 50, "set_ok": False, "emoji": "🍽️", "tags": [],
        }
        # 기존 메뉴는 요청에 포함된 필드만 바꾸고, 허용된 이름만 DB 컬럼으로 바꾼다.
        db_fields = self._to_db_fields({key: value for key, value in fields.items() if key in MENU_FIELDS})
        values.update(db_fields)
        values["tags"] = self.db.to_list(values["tags"])

        existing = self.db.one("SELECT sort_order FROM menus WHERE id=?", (menu_id,))
        if sort is not None:
            sort_order = sort
        elif existing is not None:
            sort_order = existing["sort_order"]
        else:
            next_order = self.db.one("SELECT COALESCE(MAX(sort_order) + 1, 0) AS next_order FROM menus")
            sort_order = next_order["next_order"]

        columns = tuple(values)
        insert_columns = ("id", *columns, "sort_order")
        update_fields = [f"{column}=excluded.{column}" for column in db_fields]
        update_fields.append("sort_order=excluded.sort_order")
        sql = (
            f"INSERT INTO menus ({', '.join(insert_columns)}) "
            f"VALUES ({', '.join(['?'] * len(insert_columns))}) "
            f"ON CONFLICT(id) DO UPDATE SET {', '.join(update_fields)}"
        )
        params = (menu_id, *(values[column] for column in columns), sort_order)
        self.db.run(sql, params)

        saved_menu = self.menu(menu_id)
        if saved_menu is None:
            raise RuntimeError("저장한 메뉴를 다시 조회하지 못했습니다.")
        return saved_menu

    def delete_menu(self, menu_id: str) -> bool:
        """메뉴를 지우고, 삭제 대상이 있었으면 True를 돌려준다."""
        # DELETE 실행 결과만으로는 삭제 행 수를 알 수 없어 먼저 메뉴 존재 여부를 확인한다.
        if self.db.one("SELECT id FROM menus WHERE id=?", (menu_id,)) is None:
            return False
        self.db.run("DELETE FROM menus WHERE id=?", (menu_id,))
        return True
