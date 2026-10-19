"""룰렛 칸 설정 저장소. 관리자와 손님 룰렛이 같은 테이블을 사용한다."""

from __future__ import annotations

import json
from pathlib import Path

from app.stores.db import Database
from app.stores.shop_menus import EVENT_DEFAULT_IDS

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

    def _service_allowed(self, menu_id: str, is_event: bool | None) -> bool:
        """이벤트로 체크한 메뉴만 서비스 경품으로 허용한다.

        is_event 가 None 이면(DB에 컬럼이 없음) 예전처럼 정해 둔 기본 메뉴만 허용한다.
        이미 저장된 룰렛 칸의 메뉴는 체크가 풀려도 계속 허용해, 같은 설정을 다시 저장할 수 있게 한다."""
        if is_event is None:
            is_event = menu_id in EVENT_DEFAULT_IDS
        return bool(is_event) or self.db.one("SELECT id FROM roulette_prizes WHERE menu_id=?", (menu_id,)) is not None

    def service_menu_exists(self, menu_id: str) -> bool:
        """메뉴 담당 DB 전환 전에는 시드, 전환 후에는 DB 메뉴를 같은 기준으로 검사한다."""
        has_event_column = "is_event" in self.db.columns("menus")
        event_sql = "is_event" if has_event_column else "0 AS is_event"
        row = self.db.one(f"SELECT id, {event_sql} FROM menus WHERE id=?", (menu_id,))
        if row:
            return self._service_allowed(menu_id, row["is_event"] if has_event_column else None)
        in_seed = any(menu["id"] == menu_id for menu in json.loads(MENU_SEED_PATH.read_text(encoding="utf-8")))
        return in_seed and self._service_allowed(menu_id, None)

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
