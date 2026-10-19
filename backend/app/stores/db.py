"""DB 연결 공용 래퍼 (프로토타입: 단일 연결 + 락). 저장소들이 같은 DB를 나눠 쓴다.

DATABASE_URL 이 sqlite:/// 로 시작하면 SQLite, postgresql:// 로 시작하면 Postgres(Supabase)를 쓴다.
저장소의 SQL 은 SQLite 문법(? 자리표시자, AUTOINCREMENT)으로 쓰고, Postgres 에서는 아래 translate() 가 바꿔 준다.
"""

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone

SERIAL_TABLES = {"members", "orders", "order_items", "order_item_components", "staff_calls", "recommendation_events", "sms_logs", "coupons",
                 "table_logins",
                 # 아래 5개는 스키마(docs/db/fbgrowth_schema.sql)에서 id 가 자동 증가지만 아직 INSERT 하는 코드가 없던 테이블.
                 # 여기에 없으면 Postgres 에서 INSERT 뒤 id 가 None 으로 돌아오므로 미리 넣어 둔다.
                 "roulette_prizes", "staff_call_items", "quiz_options", "chat_messages", "alerts"}  # id 가 자동 증가인 테이블


def is_postgres(url: str) -> bool:
    return url.startswith(("postgres://", "postgresql://"))


def translate(sql: str) -> str:
    """SQLite 문법의 SQL 을 Postgres 문법으로 바꾼다."""
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    return sql.replace("%", "%%").replace("?", "%s")


def _plain(v):
    """Postgres 가 돌려준 시각은 SQLite 와 같은 ISO 문자열로 맞춘다 (화면·통계 코드가 문자열을 기대한다)."""
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat(timespec="seconds")
    return v.isoformat() if isinstance(v, date) else v


class Database:
    def __init__(self, database_url: str = "sqlite:///:memory:"):
        self.pg = is_postgres(database_url)
        self._url = database_url
        self._lock = threading.Lock()
        self._conn = self._connect()

    def _connect(self):
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            # prepare_threshold=None: Supabase 풀러(트랜잭션 모드)는 prepared statement 를 지원하지 않는다.
            return psycopg.connect(self._url, row_factory=dict_row, prepare_threshold=None, autocommit=True,
                                   # 연결이 반쯤 끊겨 쿼리가 영원히 멈추는 것을 막는다: 연결 10초 제한 + 유휴 연결 생존 확인(keepalive).
                                   connect_timeout=10, keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3)
        conn = sqlite3.connect(self._url.removeprefix("sqlite:///") or ":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple = ()):
        """Postgres 는 연결이 끊겼으면(풀러 유휴 종료 등) 한 번 다시 연결해서 재시도한다."""
        if not self.pg:
            return self._conn.execute(sql, params)
        import psycopg
        sql = translate(sql)
        try:
            return self._conn.execute(sql, params)
        except psycopg.OperationalError:
            if not self._conn.closed:
                raise
            self._conn = self._connect()
            return self._conn.execute(sql, params)

    def run(self, sql: str, params: tuple = ()) -> int | None:
        """실행하고, INSERT 면 새 행의 id 를 돌려준다."""
        with self._lock:
            if self.pg:
                m = re.match(r"\s*INSERT\s+INTO\s+(\w+)", sql, re.I)
                if m and m.group(1).lower() in SERIAL_TABLES:
                    row = self._execute(sql + " RETURNING id", params).fetchone()
                    return row["id"] if row else None
                self._execute(sql, params)
                return None
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [{k: _plain(v) for k, v in dict(r).items()} for r in self._execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def script(self, sql: str) -> None:
        with self._lock:
            if self.pg:
                for stmt in filter(None, (s.strip() for s in sql.split(";"))):
                    self._execute(stmt)
                return
            self._conn.executescript(sql)
            self._conn.commit()

    def atomic(self, statements: list[tuple[str, tuple]]) -> None:
        """여러 변경을 한 트랜잭션으로 실행한다. 하나라도 실패하면 전부 이전 상태로 되돌린다."""
        with self._lock:
            if self.pg:
                with self._conn.transaction():
                    for sql, params in statements:
                        self._execute(sql, params)
                return
            try:
                for sql, params in statements:
                    self._conn.execute(sql, params)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @contextmanager
    def transaction(self):
        """저장소가 여러 INSERT를 하나의 트랜잭션으로 실행할 때 쓰는 문맥 관리자."""
        with self._lock:
            if self.pg:
                with self._conn.transaction():
                    yield
                return
            try:
                yield
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def to_list(self, value) -> str | list:
        """목록 컬럼에 넣을 값: Postgres 는 배열(text[]), SQLite 는 JSON 문자열."""
        return list(value) if self.pg else json.dumps(list(value), ensure_ascii=False)

    @staticmethod
    def from_list(value) -> list:
        return json.loads(value) if isinstance(value, str) else list(value or [])

    def columns(self, table: str) -> set[str]:
        """테이블의 컬럼 이름 (스키마 마이그레이션 확인용)."""
        if self.pg:
            rows = self.all("SELECT column_name AS name FROM information_schema.columns "
                            "WHERE table_schema='public' AND table_name=?", (table,))
        else:
            rows = self.all(f"PRAGMA table_info({table})")
        return {r["name"] for r in rows}
