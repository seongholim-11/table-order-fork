"""고객 등급 기준 한 행을 저장한다. 회원 등급 자체는 방문 기록으로 계산한다."""

import json
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.settings import Settings
from app.stores.db import Database

# SQLite 테스트에서도 Supabase의 기존 app_settings와 같은 저장 계약을 사용한다.
SCHEMA = """CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"""


class GradeRule(BaseModel):
    """잘못된 기준을 저장해 모든 고객 분류가 달라지는 일을 막는다."""
    model_config = ConfigDict(extra="forbid", strict=True)
    repeat: int = Field(ge=2)
    regular: int = Field(ge=3)
    dormant: int = Field(ge=1)

    @model_validator(mode="after")
    def check_order(self):
        if self.regular <= self.repeat:
            raise ValueError("단골 기준은 재방문 기준보다 커야 합니다.")
        return self


class GradeRuleStore:
    def __init__(self, db: Database):
        self.db = db

    def initialize(self):
        """실제 Supabase에는 테이블이 이미 있으므로 로컬 SQLite만 준비한다."""
        if not self.db.pg:
            self.db.script(SCHEMA)

    def get(self) -> dict | None:
        row = self.db.one("SELECT value FROM app_settings WHERE key='grade_rule'")
        if row is None:
            return None
        # jsonb는 dict, SQLite의 TEXT는 문자열로 돌아온다.
        value = json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
        return GradeRule.model_validate(value).model_dump()

    def resolve(self, settings: Settings) -> dict:
        """저장된 기준이 없을 때만 환경 변수·코드 기본값으로 돌아간다."""
        saved = self.get()
        return saved if saved is not None else {
            "repeat": settings.grade_repeat_visits, "regular": settings.grade_regular_visits,
            "dormant": settings.grade_dormant_days,
        }

    def save(self, rule: dict) -> dict:
        """단일 upsert로 저장해 조회 도중 일부 값만 바뀌는 일을 막는다."""
        valid = GradeRule.model_validate(rule).model_dump()
        value = json.dumps(valid)
        placeholder = "CAST(? AS jsonb)" if self.db.pg else "?"
        self.db.run(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('grade_rule', " + placeholder + ", ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (value, datetime.now(timezone.utc).isoformat(timespec="microseconds")))
        return valid
