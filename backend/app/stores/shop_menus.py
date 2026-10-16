"""메뉴 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). [뼈대] 시그니처와 스키마만 남겼다."""

MENU_FIELDS = ("name", "cat", "price", "desc", "image_url", "soldout", "spicy", "weight", "set_ok", "emoji", "tags")

# 컬럼 이름은 Supabase 스키마(db/fbgrowth_schema.sql)를 따른다. 밖으로는 예전 키(cat, desc, soldout)로 내보낸다.
SCHEMA = """
CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY, category_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '🍽️', tags TEXT NOT NULL DEFAULT '[]',
    is_soldout INTEGER NOT NULL DEFAULT 0, spicy INTEGER NOT NULL DEFAULT 0, weight INTEGER NOT NULL DEFAULT 50,
    set_ok INTEGER NOT NULL DEFAULT 0, image_url TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
"""


class MenuMixin:
    def seed_menus(self) -> None:
        """메뉴 테이블이 비어 있을 때만 seed/menu.json 을 넣는다.

        TODO: menus 가 비어 있으면 seed/menu.json 을 읽어 save_menu(id, menu, sort=순번) 로 넣는다."""
        raise NotImplementedError

    def menus(self) -> list[dict]:
        """TODO: 정렬(sort_order, id)된 전체 메뉴. 컬럼 category_id→cat, description→desc, is_soldout→soldout 로 이름을 바꿔
        내보내고 tags 는 db.from_list, soldout·set_ok 는 bool 로 만든다."""
        raise NotImplementedError

    def menu(self, menu_id: str) -> dict | None:
        """TODO: 한 건 조회, 없으면 None."""
        raise NotImplementedError

    def save_menu(self, menu_id: str, fields: dict, sort: int | None = None) -> dict:
        """있으면 주어진 필드(MENU_FIELDS)만 수정, 없으면 기본값을 채워 새로 만든다.

        TODO: INSERT ... ON CONFLICT(id) DO UPDATE. sort 가 없으면 기존 sort_order, 새 메뉴면 MAX(sort_order)+1.
        TODO: 저장한 메뉴를 menu() 로 읽어 반환."""
        raise NotImplementedError

    def delete_menu(self, menu_id: str) -> bool:
        """TODO: 지우고, 있었으면 True 없었으면 False."""
        raise NotImplementedError
