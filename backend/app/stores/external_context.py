"""외부 정보(오늘 날씨·행사 문구) 저장소. 하루에 한 번만 외부 API를 부르도록 결과를 날짜별로 저장해 둔다."""

from app.stores.db import Database
from app.stores.members import now_iso

# 운영 DB(Supabase)에는 docs/db/fbgrowth_schema.sql 로 이미 만들어져 있다. 아래는 로컬 SQLite·테스트용이다.
SCHEMA = """\
CREATE TABLE IF NOT EXISTS external_context (
    day          TEXT PRIMARY KEY,
    weather_text TEXT NOT NULL DEFAULT '',
    event_text   TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class ExternalContextStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)

    def get(self, day: str) -> dict | None:
        """그날(YYYY-MM-DD) 저장된 날씨·행사 문구. 없으면 None."""
        return self.db.one("SELECT weather_text, event_text FROM external_context WHERE day=?", (day,))

    def save(self, day: str, weather_text: str, event_text: str) -> None:
        """그날 행이 있으면 덮어쓰고 없으면 새로 넣는다."""
        self.db.run(
            "INSERT INTO external_context (day, weather_text, event_text, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET weather_text=excluded.weather_text, "
            "event_text=excluded.event_text, updated_at=excluded.updated_at",
            (day, weather_text, event_text, now_iso()))
