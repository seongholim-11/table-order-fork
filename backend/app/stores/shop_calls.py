"""직원 호출 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 테이블은 staff_calls (처리 화면은 없어 done 은 done_at 으로 보관)."""

from app.stores.members import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, table_no INTEGER NOT NULL, items TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, done_at TEXT);
"""

SELECT = "SELECT id, created_at AS ts, table_no, items, done_at FROM staff_calls"


class CallMixin:
    def add_call(self, table_no: int, items: list[str]) -> dict:
        cid = self.db.run("INSERT INTO staff_calls (table_no, items, created_at) VALUES (?,?,?)",
                          (table_no, self.db.to_list(items), now_iso()))
        return self.call(cid)

    def call(self, call_id: int) -> dict:
        r = self.db.one(SELECT + " WHERE id=?", (call_id,))
        r["items"], r["done"] = self.db.from_list(r["items"]), r.pop("done_at") is not None
        return r

    def calls(self) -> list[dict]:
        return [self.call(r["id"]) for r in self.db.all("SELECT id FROM staff_calls ORDER BY id DESC")]

    def finish_call(self, call_id: int) -> dict | None:
        if not self.db.one("SELECT 1 FROM staff_calls WHERE id=?", (call_id,)):
            return None
        self.db.run("UPDATE staff_calls SET done_at=? WHERE id=?", (now_iso(), call_id))
        return self.call(call_id)
