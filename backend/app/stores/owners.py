"""사장님(owners) 저장소. Supabase Auth 사용자 중 관리자 화면에 들어갈 수 있는 계정을 기록한다.

Supabase 에는 owners 테이블이 이미 있고(user_id uuid), 로컬 SQLite 에서는 같은 이름의 간단한 테이블을 만든다.
"""

import time

from app.stores.db import Database

SCHEMA = """\
CREATE TABLE IF NOT EXISTS owners (
    user_id    TEXT PRIMARY KEY,
    role       TEXT NOT NULL DEFAULT 'OWNER',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
CACHE_SECONDS = 60  # 관리자 화면은 요청이 많아서, 같은 토큰의 확인 결과를 잠시 기억해 Supabase 호출을 줄인다


class OwnerStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        self._cache: dict[str, tuple[float, str | None]] = {}  # {토큰: (확인 시각, 사장님 id 또는 None)}

    def is_owner(self, user_id: str) -> bool:
        # uuid 컬럼(Supabase)과 TEXT 컬럼(SQLite)을 모두 비교할 수 있게 문자열로 바꿔서 찾는다.
        return self.db.one("SELECT 1 AS ok FROM owners WHERE CAST(user_id AS TEXT)=?", (user_id,)) is not None

    def owner_id_from_token(self, token: str, supabase) -> str | None:
        """Supabase 액세스 토큰이 유효하고 owners 에 있는 계정이면 그 id, 아니면 None."""
        saved = self._cache.get(token)
        if saved and time.monotonic() - saved[0] < CACHE_SECONDS:
            return saved[1]
        user_id = supabase.get_user_id(token)
        owner_id = user_id if user_id and self.is_owner(user_id) else None
        self._cache[token] = (time.monotonic(), owner_id)
        return owner_id
