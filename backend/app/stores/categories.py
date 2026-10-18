"""카테고리 목록과 관리자 변경 사항을 DB에 저장한다."""

import builtins
import json
from pathlib import Path

from app.stores.db import Database

SCHEMA = """\
CREATE TABLE IF NOT EXISTS categories (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    icon        TEXT NOT NULL DEFAULT '🍽️',
    color_from  TEXT NOT NULL DEFAULT '#a29bfe',
    color_to    TEXT NOT NULL DEFAULT '#4b3f9e',
    is_virtual  INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
"""
class CategoryError(ValueError):
    """화면에 그대로 보여 줄 수 있는 카테고리 검증 오류."""


class CategoryStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        self.seed_if_empty()

    def seed_if_empty(self) -> None:
        """DB가 비어 있을 때만 기존 콘텐츠 파일의 목록으로 초기화한다."""
        if self.db.one("SELECT id FROM categories LIMIT 1"):
            return
        seed_path = Path(__file__).resolve().parent.parent / "seed" / "content.json"
        with open(seed_path, encoding="utf-8") as file:
            categories = json.load(file).get("categories", [])
        for sort_order, category in enumerate(categories):
            colors = category.get("colors", ["#a29bfe", "#4b3f9e"])
            self.db.run(
                "INSERT INTO categories (id, name, icon, color_from, color_to, is_virtual, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (category["id"], category["name"], category.get("icon", "🍽️"), colors[0], colors[1],
                 category["id"] in ("ai", "best"), sort_order),
            )

    def list(self, include_count: bool = False) -> builtins.list[dict]:
        """카테고리를 표시 순서로 반환하고, 요청되면 메뉴 개수도 함께 계산한다."""
        rows = self.db.all(
            "SELECT c.id, c.name, c.icon, c.color_from, c.color_to, c.is_virtual, c.sort_order, "
            "(SELECT COUNT(*) FROM menus m WHERE m.category_id=c.id) AS menu_count "
            "FROM categories c ORDER BY c.sort_order, c.id"
        )
        result = []
        for row in rows:
            category = {
                "id": row["id"], "name": row["name"], "icon": row["icon"],
                "colors": [row["color_from"], row["color_to"]],
            }
            if include_count:
                category["menu_count"] = row["menu_count"]
                category["is_virtual"] = bool(row["is_virtual"])
            result.append(category)
        return result

    def add(self, category_id: str, name: str, icon: str, colors: builtins.list[str]) -> dict:
        name = self._clean_name(name)
        if self.db.one("SELECT id FROM categories WHERE id=?", (category_id,)):
            raise CategoryError("이미 사용 중인 카테고리 ID입니다.")
        if self.db.one("SELECT id FROM categories WHERE lower(name)=lower(?)", (name,)):
            raise CategoryError(f"'{name}' 카테고리가 이미 있어요.")
        row = self.db.one("SELECT COALESCE(MAX(sort_order) + 1, 0) AS next_order FROM categories")
        self.db.run(
            "INSERT INTO categories (id, name, icon, color_from, color_to, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
            (category_id, name, icon, colors[0], colors[1], row["next_order"]),
        )
        return self.get(category_id)

    def update(self, category_id: str, fields: dict) -> dict | None:
        current = self.db.one("SELECT id, name, icon, color_from, color_to, is_virtual FROM categories WHERE id=?", (category_id,))
        if current is None:
            return None
        if current["is_virtual"]:
            raise CategoryError("가상 카테고리는 수정할 수 없습니다.")
        name = self._clean_name(fields.get("name", current["name"]))
        if self.db.one("SELECT id FROM categories WHERE lower(name)=lower(?) AND id<>?", (name, category_id)):
            raise CategoryError(f"'{name}' 카테고리가 이미 있어요.")
        colors = fields.get("colors", [current["color_from"], current["color_to"]])
        self.db.run(
            "UPDATE categories SET name=?, icon=?, color_from=?, color_to=? WHERE id=?",
            (name, fields.get("icon", current["icon"]), colors[0], colors[1], category_id),
        )
        return self.get(category_id)

    def delete(self, category_id: str) -> tuple[bool, int]:
        current = self.db.one("SELECT is_virtual FROM categories WHERE id=?", (category_id,))
        if current is None:
            return False, 0
        if current["is_virtual"]:
            raise CategoryError("가상 카테고리는 삭제할 수 없습니다.")
        count = self.db.one("SELECT COUNT(*) AS count FROM menus WHERE category_id=?", (category_id,))["count"]
        if count:
            return True, count
        self.db.run("DELETE FROM categories WHERE id=?", (category_id,))
        return True, 0

    def get(self, category_id: str) -> dict | None:
        return next((category for category in self.list() if category["id"] == category_id), None)

    @staticmethod
    def _clean_name(name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise CategoryError("카테고리 이름을 입력해 주세요.")
        return name
