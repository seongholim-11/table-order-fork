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

    def set_prize(self, table_no: int, member_id: int, prize: str, prize_id: int | None = None) -> int | None:
        """룰렛 결과를 기록한다. 이미 돌린 회원이면 덮어쓰지 않는다 (회원당 1회). [뼈대]

        prize_id: 당첨된 룰렛 칸(roulette_prizes.id). 모르면 None (prize_text 만 저장).

        TODO: 이 태블릿(table_no)의 가장 최근 로그인 기록(_cutoff 이후)을 찾아 prize_text 가 비어 있을 때만
              prize_text·prize_id·played_at 을 채우고, 기록했으면 그 table_logins 행의 id 를 돌려준다
              (coupons.issue 의 table_login_id 로 쓴다). 없거나 이미 다른 값이면 None."""
        raise NotImplementedError
