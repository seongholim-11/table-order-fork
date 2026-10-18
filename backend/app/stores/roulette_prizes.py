"""룰렛 칸 설정 저장소. 관리자와 손님 룰렛이 같은 테이블을 사용한다."""

from __future__ import annotations

import json
from pathlib import Path

from app.stores.db import Database

SCHEMA = """\
CREATE TABLE IF NOT EXISTS roulette_prizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    short_text TEXT NOT NULL,
    emoji TEXT NOT NULL DEFAULT '🎁',
    color TEXT NOT NULL,
    kind TEXT NOT NULL,
    percent INTEGER,
    menu_id TEXT,
    weight REAL NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "roulette_prizes.json"
MENU_SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "menu.json"
SERVICE_MENU_IDS = {"a1", "a4", "a11", "d7", "d8", "d1", "j1", "b1"}


class RoulettePrizeStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        """새 DB에서만 기본 룰렛 칸을 넣어 관리자·손님 화면이 바로 뜨게 한다."""
        if self.db.one("SELECT id FROM roulette_prizes LIMIT 1") is None:
            self.replace(json.loads(SEED_PATH.read_text(encoding="utf-8")))

    def list(self) -> list[dict]:
        rows = self.db.all("SELECT label, short_text, emoji, color, kind, percent, menu_id, weight "
                           "FROM roulette_prizes ORDER BY sort_order, id")
        return [{"label": row["label"], "short": row["short_text"], "emoji": row["emoji"],
                 "color": row["color"], "kind": row["kind"], "weight": float(row["weight"]),
                 **({"percent": row["percent"]} if row["kind"] == "discount" else {"item_id": row["menu_id"]})}
                for row in rows]

    @staticmethod
    def _service_allowed(menu: dict) -> bool:
        """사장님이 정한 맛보기·간식·음료 메뉴만 서비스 경품으로 허용한다."""
        return menu["id"] in SERVICE_MENU_IDS

    def service_menu_exists(self, menu_id: str) -> bool:
        """메뉴 담당 DB 전환 전에는 시드, 전환 후에는 DB 메뉴를 같은 기준으로 검사한다."""
        row = self.db.one("SELECT id, category_id AS cat, name, price, is_soldout AS soldout "
                          "FROM menus WHERE id=?", (menu_id,))
        if row:
            return self._service_allowed(row)
        seed = next((menu for menu in json.loads(MENU_SEED_PATH.read_text(encoding="utf-8"))
                     if menu["id"] == menu_id), None)
        return bool(seed and self._service_allowed(seed))

    def replace(self, prizes: list[dict]) -> list[dict]:
        """칸 순서를 보존해 전체 교체한다. 중간 실패 시 기존 설정이 유지된다."""
        statements = [("DELETE FROM roulette_prizes", ())]
        for order, prize in enumerate(prizes):
            statements.append((
                "INSERT INTO roulette_prizes "
                "(label, short_text, emoji, color, kind, percent, menu_id, weight, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (prize["label"], prize["short"], prize.get("emoji", "🎁"), prize["color"], prize["kind"],
                 prize.get("percent"), prize.get("item_id"), prize.get("weight", 1), order),
            ))
        self.db.atomic(statements)
        return self.list()
