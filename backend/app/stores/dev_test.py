"""개발 흐름 확인용 test 테이블 저장소."""

from uuid import uuid4

from app.stores.db import Database


class DevTestStore:
    def __init__(self, db: Database):
        self.db = db

    def write_and_read(self) -> dict:
        """임의 값을 저장하고 같은 행을 다시 읽어 DB 쓰기·읽기가 모두 되는지 확인한다."""
        row_id = str(uuid4())
        value = str(uuid4())
        self.db.run("INSERT INTO test (id, value) VALUES (?, ?)", (row_id, value))
        saved = self.db.one("SELECT value FROM test WHERE id=?", (row_id,))
        return {"result": 1 if saved and saved["value"] == value else 0}
