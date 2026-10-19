"""메뉴 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). """

import json
from pathlib import Path

from app.stores.db import Database

MENU_FIELDS = ("name", "cat", "price", "desc", "image_url", "soldout", "spicy", "weight", "set_ok", "emoji", "tags", "is_event")

# 이벤트(룰렛 서비스 메뉴)로 쓸 수 있는 메뉴의 기본값. 운영 DB에 is_event 컬럼이 아직 없을 때와
# 마이그레이션 SQL(docs/db/fbgrowth_menus_is_event.sql)의 초기값이 이 목록과 같다.
EVENT_DEFAULT_IDS = frozenset({"a1", "a4", "a11", "d7", "d8", "d1", "j1", "b1"})

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
    is_event    INTEGER NOT NULL DEFAULT 0,
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

    def _has_event_column(self) -> bool:
        """menus.is_event 컬럼이 있는지 확인한다. 마이그레이션 전 운영 DB에서도 앱이 죽지 않게 하려는 것이다."""
        if getattr(self, "_event_column_ok", False):
            return True
        # 컬럼이 생기면(마이그레이션 실행) 서버를 다시 켜지 않아도 바로 쓰도록, 있다고 확인된 뒤에만 기억한다.
        self._event_column_ok = "is_event" in self.db.columns("menus")
        return self._event_column_ok

    def _menu_columns(self) -> str:
        """SELECT 할 컬럼 목록. is_event 컬럼이 없으면 0 으로 대신 채운다."""
        event = "is_event" if self._has_event_column() else "0 AS is_event"
        return ("id, category_id, name, description, price, emoji, tags, is_soldout, "
                f"spicy, weight, set_ok, {event}, image_url")

    def _menu_from_row(self, row: dict) -> dict:
        """DB 행을 API 필드 모양으로 바꾼다."""
        menu = self._from_db_fields(row)
        menu["tags"] = self.db.from_list(menu["tags"])
        menu["soldout"] = bool(menu["soldout"])
        menu["set_ok"] = bool(menu["set_ok"])
        # 컬럼이 없으면 예전처럼 정해 둔 기본 메뉴만 이벤트 메뉴로 본다.
        menu["is_event"] = bool(menu["is_event"]) if self._has_event_column() else menu["id"] in EVENT_DEFAULT_IDS
        return menu

    def _seed_categories(self) -> None:
        """카테고리 테이블이 있으면 메뉴 시드에 필요한 기본 카테고리를 추가한다."""
        if not self.db.columns("categories"):
            return

        seed_path = Path(__file__).resolve().parent.parent / "seed" / "content.json"
        with open(seed_path, mode="r", encoding="utf-8") as f:
            categories = json.load(f)["categories"]

        for sort, category in enumerate(categories):
            colors = category.get("colors", ["#a29bfe", "#4b3f9e"])
            # 기존 카테고리는 관리자 설정을 보존하고, 없는 카테고리만 메뉴 FK 전에 추가한다.
            self.db.run(
                "INSERT INTO categories "
                "(id, name, icon, color_from, color_to, is_virtual, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
                (
                    category["id"], category["name"], category.get("icon", "🍽️"),
                    colors[0], colors[1], category["id"] in ("ai", "best"), sort,
                ),
            )

    def menu_categories(self) -> list[dict]:
        """메뉴를 넣을 수 있는 카테고리를 DB 표시 순서로 돌려준다."""
        # 관리자 메뉴 화면은 각 카테고리에 속한 메뉴 수를 함께 보여준다.
        category_store = getattr(self, "categories", None)
        if category_store is not None:
            return [
                {"id": category["id"], "name": category["name"]}
                for category in category_store.list(include_count=True)
                if not category["is_virtual"]
            ]
        if not self.db.columns("categories"):
            # SQLite 개발 DB에는 categories 테이블이 아직 없어서 기존 콘텐츠를 사용한다.
            seed_path = Path(__file__).resolve().parent.parent / "seed" / "content.json"
            with open(seed_path, mode="r", encoding="utf-8") as f:
                categories = json.load(f)["categories"]
            return [
                {"id": category["id"], "name": category["name"]}
                for category in categories
                if category["id"] not in ("ai", "best")
            ]

        return self.db.all(
            "SELECT id, name FROM categories WHERE is_virtual = ? ORDER BY sort_order, id",
            (False,),
        )

    def seed_menus(self) -> None:
        """메뉴 테이블이 비어 있을 때만 seed/menu.json 을 넣는다."""
        if not self.menus():
            # Postgres의 menus.category_id 외래 키가 있으므로 카테고리를 먼저 준비한다.
            self._seed_categories()
            seed_path = Path(__file__).resolve().parent.parent / "seed" / "menu.json"
            with open(seed_path, mode="r", encoding="utf-8") as f:
                menus = json.load(f)

            for sort, menu in enumerate(menus):
                # 처음 넣는 메뉴는 기본 이벤트 메뉴만 체크해 둔다.
                self.save_menu(menu_id=menu["id"], fields={**menu, "is_event": menu["id"] in EVENT_DEFAULT_IDS}, sort=sort)

    def menus(self) -> list[dict]:
        """정렬(sort_order, id)된 전체 메뉴. DB 컬럼명을 API 필드명(cat·desc·soldout)으로 바꿔 돌려준다."""
        rows = self.db.all(f"SELECT {self._menu_columns()} FROM menus ORDER BY sort_order, id")
        # DB 컬럼명을 기존 API 필드명으로 바꾸고, 화면에서 쓰기 좋은 자료형으로 변환한다.
        return [self._menu_from_row(row) for row in rows]

    def menu(self, menu_id: str) -> dict | None:
        """메뉴 ID로 한 건을 조회하고 API 필드 모양으로 돌려준다."""
        row = self.db.one(f"SELECT {self._menu_columns()} FROM menus WHERE id=?", (menu_id,))
        if row is None:
            return None

        # DB 컬럼명과 자료형을 손님·관리자 API가 쓰는 모양으로 바꾼다.
        return self._menu_from_row(row)

    def save_menu(self, menu_id: str, fields: dict | list[dict], sort: int | None = None):
        """한 메뉴 또는 여러 메뉴를 만들거나 수정하고, 변경 전체를 한 트랜잭션으로 저장한다."""
        is_batch = isinstance(fields, list)
        items = fields if is_batch else [{"id": menu_id, **fields}]
        ids = [item.get("id") for item in items]
        if not items or any(not isinstance(item_id, str) or not item_id.strip() for item_id in ids):
            raise ValueError("저장할 메뉴마다 ID가 필요합니다.")
        if len(ids) != len(set(ids)):
            raise ValueError("같은 메뉴 ID를 한 요청에서 여러 번 저장할 수 없습니다.")

        has_event_column = self._has_event_column()
        next_order = self.db.one("SELECT COALESCE(MAX(sort_order) + 1, 0) AS next_order FROM menus")["next_order"]
        statements = []
        saved_ids, deleted_ids = [], []
        for item in items:
            item_id = item["id"]
            if item.get("delete") is True:
                if set(item) - {"id", "delete"}:
                    raise ValueError("삭제 항목에는 ID와 delete만 보낼 수 있습니다.")
                if self.db.one("SELECT id FROM menus WHERE id=?", (item_id,)) is None:
                    raise ValueError(f"메뉴를 찾을 수 없습니다: {item_id}")
                statements.append(("DELETE FROM menus WHERE id=?", (item_id,)))
                deleted_ids.append(item_id)
                continue

            # 새 메뉴는 기본값을 채우고, 기존 메뉴는 전달받은 필드만 바꾼다.
            values = {
                "category_id": "side", "name": "새 메뉴", "price": 0,
                "description": "", "image_url": "", "is_soldout": False,
                "spicy": 0, "weight": 50, "set_ok": False, "emoji": "🍽️", "tags": [],
                "is_event": False,
            }
            db_fields = self._to_db_fields({key: value for key, value in item.items() if key in MENU_FIELDS})
            values.update(db_fields)
            if not has_event_column:
                # 마이그레이션 전 DB에는 컬럼이 없으므로 이벤트 값은 저장하지 않고 나머지만 저장한다.
                values.pop("is_event")
                db_fields.pop("is_event", None)
            values["tags"] = self.db.to_list(values["tags"])

            existing = self.db.one("SELECT sort_order FROM menus WHERE id=?", (item_id,))
            if not is_batch and sort is not None:
                sort_order = sort
            elif existing is not None:
                sort_order = existing["sort_order"]
            else:
                sort_order = next_order
                next_order += 1

            columns = tuple(values)
            insert_columns = ("id", *columns, "sort_order")
            update_fields = [f"{column}=excluded.{column}" for column in db_fields]
            update_fields.append("sort_order=excluded.sort_order")
            sql = (
                f"INSERT INTO menus ({', '.join(insert_columns)}) "
                f"VALUES ({', '.join(['?'] * len(insert_columns))}) "
                f"ON CONFLICT(id) DO UPDATE SET {', '.join(update_fields)}"
            )
            params = (item_id, *(values[column] for column in columns), sort_order)
            statements.append((sql, params))
            saved_ids.append(item_id)

        # 수정과 삭제 SQL을 한 번에 실행해 중간 오류 때 전체를 롤백한다.
        self.db.atomic(statements)
        saved = [self.menu(item_id) for item_id in saved_ids]
        if any(menu is None for menu in saved):
            raise RuntimeError("저장한 메뉴를 다시 조회하지 못했습니다.")
        if is_batch:
            return {"saved": len(saved), "deleted": len(deleted_ids), "menus": saved}
        return saved[0]

    def delete_menu(self, menu_id: str) -> bool:
        """메뉴를 지우고, 삭제 대상이 있었으면 True를 돌려준다."""
        # DELETE 실행 결과만으로는 삭제 행 수를 알 수 없어 먼저 메뉴 존재 여부를 확인한다.
        if self.db.one("SELECT id FROM menus WHERE id=?", (menu_id,)) is None:
            return False
        self.db.run("DELETE FROM menus WHERE id=?", (menu_id,))
        return True
