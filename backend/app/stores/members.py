"""회원 저장소."""

from datetime import datetime, timezone

from app.stores.db import Database

SCHEMA = """\
CREATE TABLE IF NOT EXISTS members (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    kakao_id             TEXT UNIQUE NOT NULL,
    nickname             TEXT NOT NULL,
    phone                TEXT,
    gender               TEXT,
    birthday             TEXT,
    birth_year           INTEGER,
    marketing_consent    INTEGER NOT NULL DEFAULT 0,
    marketing_consent_at TEXT,
    opted_out            INTEGER NOT NULL DEFAULT 0,
    opted_out_at         TEXT,
    visit_count          INTEGER NOT NULL DEFAULT 0,
    last_visit_at        TEXT,
    created_at           TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemberStore:
    def __init__(self, db: Database | str = "sqlite:///:memory:"):
        self.db = db if isinstance(db, Database) else Database(db)
        self.db.script(SCHEMA)

    def upsert_login(self, kakao_id: str, nickname: str, gender: str | None = None,
                     birthday: str | None = None, birth_year: int | None = None, phone: str | None = None) -> dict:
        """카카오 로그인 때마다 호출: 없으면 가입, 있으면 방문 횟수와 마지막 방문일을 갱신."""
        now = now_iso()
        self.db.run(
            """INSERT INTO members (kakao_id, nickname, gender, birthday, birth_year, phone, visit_count, last_visit_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
               ON CONFLICT(kakao_id) DO UPDATE SET nickname=excluded.nickname,
                 gender=COALESCE(excluded.gender, members.gender), birthday=COALESCE(excluded.birthday, members.birthday),
                 birth_year=COALESCE(excluded.birth_year, members.birth_year), phone=COALESCE(excluded.phone, members.phone),
                 visit_count=members.visit_count+1, last_visit_at=excluded.last_visit_at""",
            (kakao_id, nickname, gender, birthday, birth_year, phone, now, now))
        return self.get_by_kakao(kakao_id)

    def get_by_kakao(self, kakao_id: str) -> dict:
        return self.db.one("SELECT * FROM members WHERE kakao_id=?", (kakao_id,))

    def get(self, member_id: int) -> dict | None:
        return self.db.one("SELECT * FROM members WHERE id=?", (member_id,))

    def all(self) -> list[dict]:
        return self.db.all("SELECT * FROM members ORDER BY id")

    def set_marketing_consent(self, member_id: int, consent: bool) -> dict | None:
        """로그인할 때 받은 광고성 문자 수신 동의 여부를 저장한다. 동의하면 수신거부 상태도 해제한다."""
        self.db.run("UPDATE members SET marketing_consent=?, marketing_consent_at=?, opted_out=CASE WHEN ? THEN FALSE ELSE opted_out END WHERE id=?",
                    (consent, now_iso() if consent else None, consent, member_id))
        return self.get(member_id)

    def opt_out(self, member_id: int) -> dict | None:
        self.db.run("UPDATE members SET opted_out=TRUE, opted_out_at=? WHERE id=?", (now_iso(), member_id))
        return self.get(member_id)
