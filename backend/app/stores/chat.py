"""AI 챗봇 대화방(chat_sessions)과 말풍선(chat_messages) 저장소. SQL 은 여기에만 둔다."""

import uuid
from datetime import datetime, timedelta, timezone

from app.stores.db import Database

# 운영 DB(Supabase)에는 docs/db/fbgrowth_schema.sql 로 이미 만들어져 있다. 아래는 로컬 SQLite·테스트용이다.
SCHEMA = """\
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '새 대화',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    """같은 초에 만든 대화방도 최근순이 맞도록 마이크로초까지 저장한다."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


TITLE_MAX = 20  # 첫 질문을 대화방 제목으로 쓸 때 자르는 길이


class ChatStore:
    def __init__(self, db: Database, owner_id: str):
        self.db = db
        # 관리자 인증을 붙이기 전까지는 모든 대화방의 주인을 설정값(CHAT_OWNER_ID) 한 명으로 쓴다.
        self.owner_id = owner_id
        if not db.pg:  # Postgres 에는 테이블이 이미 있으므로 로컬 SQLite 일 때만 만든다
            db.script(SCHEMA)

    def _next_timestamp(self, owner_id: str) -> str:
        """같은 순간에 만들어진 대화방도 최근 대화방 순서가 유지되게 시각을 만든다."""
        current = datetime.now(timezone.utc)
        latest = self.db.one("SELECT MAX(updated_at) AS updated_at FROM chat_sessions WHERE owner_id=?", (owner_id,))
        if latest and latest["updated_at"]:
            try:
                previous = datetime.fromisoformat(latest["updated_at"])
                if current <= previous:
                    current = previous + timedelta(microseconds=1)
            except (TypeError, ValueError):
                # 기존 데이터 형식이 다르면 현재 시각을 그대로 사용한다.
                pass
        return current.isoformat(timespec="microseconds")

    def create_session(self) -> str:
        """새 대화방을 만들고 id(uuid 문자열)를 돌려준다. uuid 는 DB 가 아니라 코드에서 만든다."""
        session_id, now = str(uuid.uuid4()), self._next_timestamp(self.owner_id)
        self.db.run("INSERT INTO chat_sessions (id, owner_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (session_id, self.owner_id, "새 대화", now, now))
        return session_id

    def list_sessions(self) -> list[dict]:
        """내 대화방 목록. 최근에 대화한 순서이고, 마지막 메시지 시각은 updated_at 이다."""
        return self.db.all("SELECT id, title, created_at, updated_at FROM chat_sessions "
                           "WHERE owner_id=? ORDER BY updated_at DESC, created_at DESC", (self.owner_id,))

    def get_session(self, session_id: str) -> dict | None:
        """대화방 한 개와 그 메시지 전체(오래된 순). 없으면 None."""
        session = self.db.one("SELECT id, title, created_at, updated_at FROM chat_sessions "
                              "WHERE id=? AND owner_id=?", (session_id, self.owner_id))
        if session is None:
            return None
        session["messages"] = self.messages(session_id)
        return session

    def messages(self, session_id: str) -> list[dict]:
        return self.db.all("SELECT id, role, content, created_at FROM chat_messages "
                           "WHERE session_id=? ORDER BY id", (session_id,))

    def add_messages(self, session_id: str, items: list[tuple[str, str]]) -> None:
        """(역할, 내용) 목록을 한 번에 저장하고 대화방의 마지막 대화 시각을 갱신한다."""
        now = now_iso()
        for role, content in items:
            self.db.run("INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                        (session_id, role, content, now))
        self.db.run("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))

    def set_title(self, session_id: str, title: str) -> None:
        self.db.run("UPDATE chat_sessions SET title=? WHERE id=?", (title, session_id))

    def delete_session(self, session_id: str) -> bool:
        """대화방을 지운다. 메시지는 ON DELETE CASCADE 로 같이 지워지지만, SQLite 는 외래키가 꺼져 있어 직접 지운다."""
        if self.db.one("SELECT id FROM chat_sessions WHERE id=? AND owner_id=?", (session_id, self.owner_id)) is None:
            return False
        self.db.run("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        self.db.run("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        return True
