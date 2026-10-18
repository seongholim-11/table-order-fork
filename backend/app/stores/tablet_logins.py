"""태블릿(테이블)별 로그인 기록. 새로고침해도 '이 태블릿에서 로그인한 회원'과 룰렛 사용 여부를 되살리는 데 쓴다.

Supabase 의 table_logins 테이블을 쓴다 (회원·테이블·로그인 날짜(KST)당 한 줄).
기록은 JWT 유효 시간(window_minutes) 동안만 유효하다 (그 뒤엔 토큰도 만료되므로 새 손님으로 본다).
"""

from datetime import datetime, timedelta, timezone

from app.services.grades import KST
from app.stores.db import Database


SCHEMA = """\
CREATE TABLE IF NOT EXISTS table_logins (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no         INTEGER NOT NULL,
    member_id        INTEGER NOT NULL,
    login_day        TEXT NOT NULL,
    logged_in_at     TEXT NOT NULL,
    roulette_eligible INTEGER NOT NULL DEFAULT 1,
    prize_id         INTEGER,
    prize_text       TEXT,
    played_at        TEXT,
    UNIQUE (table_no, member_id, login_day)
);
CREATE UNIQUE INDEX IF NOT EXISTS table_logins_one_play_per_day
    ON table_logins (member_id, login_day) WHERE played_at IS NOT NULL;
"""


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
        """로그인 완료 시 기록한다. 같은 날 이미 있으면 그대로 둔다 (nickname 은 회원 테이블에서 읽는다).

        eligible=False 면 룰렛 기회가 없는 로그인이다 (오늘 이미 다른 테이블에서 돌린 회원)."""
        now = datetime.now(timezone.utc)
        self.db.run("INSERT INTO table_logins (table_no, member_id, login_day, logged_in_at, roulette_eligible) "
                    "VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                    (table_no, member_id, now.astimezone(KST).date().isoformat(), _iso(now), eligible))

    def list(self, table_no: int) -> list[dict]:
        rows = self.db.all("SELECT t.member_id AS id, m.nickname, t.logged_in_at AS at, t.roulette_eligible AS eligible, "
                           "t.prize_text AS prize FROM table_logins t JOIN members m ON m.id=t.member_id "
                           "WHERE t.table_no=? AND t.logged_in_at>=? ORDER BY t.logged_in_at, t.member_id",
                           (table_no, self._cutoff()))
        return [{**r, "eligible": bool(r["eligible"])} for r in rows]

    def first_valid_login_at(self, table_no: int) -> str | None:
        """주문 누적의 기준이 되는, 현재 유효한 로그인 중 가장 이른 시각을 돌려준다."""
        row = self.db.one("SELECT MIN(logged_in_at) AS since FROM table_logins "
                          "WHERE table_no=? AND logged_in_at>=?", (table_no, self._cutoff()))
        return row["since"] if row else None

    def set_prize(self, table_no: int, member_id: int, prize: str, prize_id: int | None = None) -> int | None:
        """룰렛 결과를 기록하고 기록한 로그인 행의 id를 돌려준다.

        prize_id: 당첨된 룰렛 칸(roulette_prizes.id). 모르면 None (prize_text 만 저장).
        """

        row = self.db.one(
            "SELECT id FROM table_logins WHERE table_no=? AND member_id=? AND logged_in_at>=? "
            "AND roulette_eligible=? AND prize_text IS NULL AND played_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (table_no, member_id, self._cutoff(), True),
        )
        if not row:
            return None

        played_at = _iso(datetime.now(timezone.utc))
        try:
            self.db.run(
                "UPDATE table_logins SET prize_text=?, prize_id=?, played_at=? "
                "WHERE id=? AND prize_text IS NULL AND played_at IS NULL",
                (prize, prize_id, played_at, row["id"]),
            )
        except Exception as exc:
            # 동시에 다른 테이블에서 돌리면 부분 유니크 인덱스가 막는다.
            # DB 예외를 라우터까지 내보내지 않고 '이미 처리됨'으로 통일한다.
            if "unique" not in str(exc).lower() and "duplicate" not in str(exc).lower():
                raise
            return None

        saved = self.db.one("SELECT id FROM table_logins WHERE id=? AND played_at IS NOT NULL", (row["id"],))
        return saved["id"] if saved else None
