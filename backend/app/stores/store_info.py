"""매장 정보(이름·지점·슬로건·테이블 수) 저장소. 한 줄짜리 테이블이고, 비어 있을 때만 설정값(STORE_*)으로 채운다."""

from app.core.settings import Settings
from app.stores.db import Database

SCHEMA = """CREATE TABLE IF NOT EXISTS store_info (
    id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL, branch TEXT NOT NULL,
    slogan TEXT NOT NULL DEFAULT '', tables INTEGER NOT NULL DEFAULT 30)"""


class StoreInfoStore:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        db.script(SCHEMA)
        db.run("INSERT INTO store_info (id, name, branch, slogan, tables) VALUES (1,?,?,?,?) ON CONFLICT DO NOTHING",
               (settings.store_name, settings.store_branch, settings.store_slogan, settings.store_tables))

    def get(self) -> dict:
        return self.db.one("SELECT name, branch, slogan, tables FROM store_info WHERE id=1")
