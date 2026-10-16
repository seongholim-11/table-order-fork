"""DB 연결 점검용 저장소. 서버가 실제로 Supabase(Postgres)에 붙어 있는지, 필요한 테이블이 다 있는지 확인한다.

SQL 은 stores 에만 쓰는 규칙에 따라 점검용 SELECT 도 여기에 둔다 (라우터는 이 클래스만 부른다).
"""

import time

from app.stores.db import Database

# docs/db/fbgrowth_schema.sql 이 만드는 테이블 26개 (Postgres 에서 빠진 것이 있는지 비교할 기준)
EXPECTED_TABLES = (
    "store_info", "categories", "menus", "members", "login_sessions", "roulette_prizes", "table_logins",
    "recommendation_events", "orders", "order_items", "order_item_components", "staff_call_items", "staff_calls",
    "quiz_questions", "quiz_options", "weather_types", "weather_current", "recommendation_rules", "owners",
    "app_settings", "alerts", "sms_logs", "sms_log_recipients", "external_context", "chat_sessions", "chat_messages",
    "coupons",
)
# 새 설계로 바꾸면서 쓰지 않게 된 옛 테이블. 남아 있으면 RLS 가 꺼진 채 노출될 수 있어 알려 준다.
LEGACY_TABLES = ("content", "calls", "tablet_logins")


class DbCheckStore:
    def __init__(self, db: Database):
        self.db = db

    def _table_names(self) -> set[str]:
        """지금 연결된 DB 에 있는 테이블 이름 (Postgres 는 public 스키마, SQLite 는 sqlite_master)."""
        if self.db.pg:
            rows = self.db.all("SELECT table_name AS name FROM information_schema.tables "
                               "WHERE table_schema='public' AND table_type='BASE TABLE'")
        else:
            rows = self.db.all("SELECT name FROM sqlite_master WHERE type='table'")
        return {r["name"] for r in rows}

    def check(self) -> dict:
        """연결 여부·DB 종류·버전·응답 시간·테이블 유무를 한 번에 돌려준다. 연결 정보(주소·비밀번호)는 담지 않는다."""
        started = time.perf_counter()
        try:
            version_sql = "SELECT version() AS v" if self.db.pg else "SELECT sqlite_version() AS v"
            version = self.db.one(version_sql)["v"]
            names = self._table_names()
        except Exception as e:  # 연결이 끊겼거나 권한이 없는 경우: 500 대신 원인 종류만 알려 준다
            return {"ok": False, "dialect": "postgres" if self.db.pg else "sqlite", "error": type(e).__name__}
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        missing = [t for t in EXPECTED_TABLES if t not in names]
        return {
            "ok": True,
            "dialect": "postgres" if self.db.pg else "sqlite",
            "server_version": version,
            "elapsed_ms": elapsed_ms,
            # SQLite 는 stores 가 만든 일부 테이블만 있으므로 '없는 테이블'은 Postgres 일 때만 의미가 있다
            "tables": {"expected": len(EXPECTED_TABLES), "found": len(EXPECTED_TABLES) - len(missing),
                       "missing": missing if self.db.pg else []},
            "legacy_tables": [t for t in LEGACY_TABLES if t in names],
        }
