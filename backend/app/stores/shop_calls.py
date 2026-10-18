"""직원 호출 항목과 손님 호출 기록 저장소."""

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """\
CREATE TABLE IF NOT EXISTS staff_call_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT NOT NULL UNIQUE CHECK(length(label) BETWEEN 1 AND 20),
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS staff_calls (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no   INTEGER NOT NULL,
    items      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    done_at    TEXT
);
"""

SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "staff_call_items.json"


class CallMixin:
    def seed_call_items(self) -> None:
        """새 DB에서만 기본 요청 항목을 채워 손님 호출 창이 비어 있지 않게 한다."""
        if self.db.one("SELECT id FROM staff_call_items LIMIT 1") is not None:
            return
        labels = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.db.atomic([
            ("INSERT INTO staff_call_items (label, sort_order) VALUES (?, ?)", (label, order))
            for order, label in enumerate(labels)
        ])

    def call_items(self) -> list[str]:
        """호출 창에 표시할 문자열을 관리자가 정한 순서대로 반환한다."""
        # 운영 중 항목이 모두 지워져도 다음 조회에서 기본값으로 복구한다.
        self.seed_call_items()
        return [row["label"] for row in self.db.all(
            "SELECT label FROM staff_call_items ORDER BY sort_order, id")]

    def add_call(self, table_no: int, items: list[str]) -> dict:
        """선택한 요청 항목을 저장하고 관리자 화면과 같은 응답 모양으로 돌려준다."""
        created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        call_id = self.db.run(
            "INSERT INTO staff_calls (table_no, items, created_at) VALUES (?, ?, ?)",
            (table_no, self.db.to_list(items), created_at),
        )
        return self.call(call_id)

    @staticmethod
    def _call_row(db, row: dict | None) -> dict | None:
        if row is None:
            return None
        return {"id": row["id"], "table_no": row["table_no"], "items": db.from_list(row["items"]),
                "ts": row["created_at"], "done": row["done_at"] is not None}

    def call(self, call_id: int) -> dict | None:
        """한 건을 읽고 DB 배열·완료 시각을 화면용 목록·불리언으로 바꾼다."""
        row = self.db.one(
            "SELECT id, table_no, items, created_at, done_at FROM staff_calls WHERE id=?", (call_id,))
        return self._call_row(self.db, row)

    def list_calls(self) -> list[dict]:
        """관리자가 새 호출부터 확인할 수 있도록 전체 호출을 최신순으로 반환한다."""
        rows = self.db.all(
            "SELECT id, table_no, items, created_at, done_at FROM staff_calls "
            "ORDER BY created_at DESC, id DESC")
        return [self._call_row(self.db, row) for row in rows]

    def mark_done(self, call_id: int) -> dict | None:
        """처리 시각을 한 번만 기록한다. 이미 완료된 호출도 같은 결과를 주는 멱등 처리다."""
        current = self.call(call_id)
        if current is None:
            return None
        if not current["done"]:
            self.db.run("UPDATE staff_calls SET done_at=? WHERE id=? AND done_at IS NULL",
                        (datetime.now(timezone.utc).isoformat(timespec="microseconds"), call_id))
        return self.call(call_id)
