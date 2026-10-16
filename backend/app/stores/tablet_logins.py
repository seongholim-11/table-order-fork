"""태블릿(테이블)별 로그인 기록. 새로고침해도 '이 태블릿에서 로그인한 회원'과 룰렛 사용 여부를 되살리는 데 쓴다.

기록은 JWT 유효 시간(window_minutes) 동안만 유효하다 (그 뒤엔 토큰도 만료되므로 새 손님으로 본다).
"""

from datetime import datetime, timedelta, timezone

from app.stores.db import Database

SCHEMA = """CREATE TABLE IF NOT EXISTS tablet_logins (
    table_no INTEGER NOT NULL, member_id INTEGER NOT NULL, nickname TEXT NOT NULL,
    logged_in_at TEXT NOT NULL, eligible INTEGER NOT NULL DEFAULT 1, prize TEXT,
    PRIMARY KEY (table_no, member_id))"""


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class TabletLoginStore:
    def __init__(self, db: Database, window_minutes: int = 720):
        self.db = db
        self.window = timedelta(minutes=window_minutes)
        self.db.script(SCHEMA)

    def _cutoff(self) -> str:
        return _iso(datetime.now(timezone.utc) - self.window)

    def record(self, table_no: int, member_id: int, nickname: str, eligible: bool = True) -> None:
        """로그인 완료 시 기록한다. 유효 시간이 지난 옛 기록은 지우고, 이미 있으면 그대로 둔다.

        eligible=False 면 룰렛 기회가 없는 로그인이다 (오늘 이미 다른 테이블에서 돌린 회원)."""
        self.db.run("DELETE FROM tablet_logins WHERE table_no=? AND logged_in_at<?", (table_no, self._cutoff()))
        self.db.run("INSERT INTO tablet_logins (table_no, member_id, nickname, logged_in_at, eligible) VALUES (?,?,?,?,?) "
                    "ON CONFLICT DO NOTHING",
                    (table_no, member_id, nickname, _iso(datetime.now(timezone.utc)), int(eligible)))

    def list(self, table_no: int) -> list[dict]:
        rows = self.db.all("SELECT member_id AS id, nickname, logged_in_at AS at, eligible, prize FROM tablet_logins "
                           "WHERE table_no=? AND logged_in_at>=? ORDER BY logged_in_at, member_id", (table_no, self._cutoff()))
        return [{**r, "eligible": bool(r["eligible"])} for r in rows]

    def set_prize(self, table_no: int, member_id: int, prize: str) -> bool:
        """룰렛 결과를 기록한다. 이미 돌린 회원이면 덮어쓰지 않는다 (회원당 1회)."""
        self.db.run("UPDATE tablet_logins SET prize=? WHERE table_no=? AND member_id=? AND prize IS NULL",
                    (prize, table_no, member_id))
        row = self.db.one("SELECT prize FROM tablet_logins WHERE table_no=? AND member_id=?", (table_no, member_id))
        return bool(row and row["prize"] == prize)
