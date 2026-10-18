"""AI 질문·날씨·추천 규칙 저장소.

화면이 이미 사용하던 user/*_data.py의 모양을 유지하면서, 실제 DB의 정규화된
테이블에서 읽어 API 응답을 만든다. 로컬 DB가 비어 있을 때만 화면 데이터로
초기화하므로 기존 Supabase 데이터는 덮어쓰지 않는다.
"""

import importlib.util
import json
import re
from pathlib import Path

from app.services.weather import current_weather
from app.stores.db import Database


SCHEMA = """\
CREATE TABLE IF NOT EXISTS quiz_questions (
    id          TEXT PRIMARY KEY,
    group_name  TEXT NOT NULL,
    title       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quiz_options (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id  TEXT NOT NULL,
    value        TEXT NOT NULL,
    label        TEXT NOT NULL,
    emoji        TEXT NOT NULL DEFAULT '',
    sort_order   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (question_id, value)
);
CREATE TABLE IF NOT EXISTS weather_types (
    code   TEXT PRIMARY KEY,
    label  TEXT NOT NULL,
    icon   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS weather_current (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    code        TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'dummy',
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS recommendation_rules (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _load_module(name: str, filename: str):
    """화면 더미 데이터를 시드 원본으로 읽는다(화면과 DB의 초기 모양을 맞춘다)."""
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "user" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"시드 파일을 읽을 수 없습니다: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed_data() -> tuple[list[dict], dict, dict]:
    quiz = _load_module("table_order_ai_quiz_seed", "ai_quiz_data.py")
    recommendations = _load_module("table_order_recommendation_seed", "recommendation_data.py")
    return quiz.QUESTIONS, quiz.WEATHER, recommendations.RULES


class AiContentStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        questions, weather, rules = _seed_data()
        if self.db.one("SELECT id FROM quiz_questions LIMIT 1") is None:
            for question_order, question in enumerate(questions):
                self.db.run(
                    "INSERT INTO quiz_questions (id, group_name, title, sort_order) VALUES (?, ?, ?, ?)",
                    (question["id"], question["group"], question["title"], question_order),
                )
                for option_order, option in enumerate(question["options"]):
                    # Supabase 기준 컬럼은 text이므로 숫자 선택지도 문자열로 저장하고 읽을 때 복원한다.
                    self.db.run(
                        "INSERT INTO quiz_options (question_id, value, label, emoji, sort_order) VALUES (?, ?, ?, ?, ?)",
                        (question["id"], str(option["value"]), option["label"], option["emoji"], option_order),
                    )

        if self.db.one("SELECT code FROM weather_types LIMIT 1") is None:
            for code, info in weather["types"].items():
                self.db.run("INSERT INTO weather_types (code, label, icon) VALUES (?, ?, ?)",
                            (code, info["label"], info["icon"]))
        if self.db.one("SELECT id FROM weather_current WHERE id=1") is None:
            self.db.run("INSERT INTO weather_current (id, code, source) VALUES (1, ?, 'dummy')",
                        (weather["current"],))

        if self.db.one("SELECT key FROM recommendation_rules LIMIT 1") is None:
            value_sql = "CAST(? AS jsonb)" if self.db.pg else "?"
            for key, value in rules.items():
                self.db.run(
                    "INSERT INTO recommendation_rules (key, value) VALUES (?, " + value_sql + ")",
                    (key, json.dumps(value, ensure_ascii=False)),
                )

    @staticmethod
    def _value(value: str):
        """화면 데이터의 숫자 선택지를 DB text에서 원래 int로 되돌린다."""
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        return value

    def questions(self) -> list[dict]:
        questions = self.db.all(
            "SELECT id, group_name, title FROM quiz_questions ORDER BY sort_order, id"
        )
        options = self.db.all(
            "SELECT question_id, value, label, emoji FROM quiz_options ORDER BY sort_order, id"
        )
        by_question = {question["id"]: [] for question in questions}
        for option in options:
            by_question.setdefault(option["question_id"], []).append({
                "value": self._value(option["value"]), "label": option["label"], "emoji": option["emoji"]
            })
        return [{"id": question["id"], "group": question["group_name"], "title": question["title"],
                 "options": by_question[question["id"]]} for question in questions]

    def weather_shape(self) -> dict:
        # 날씨 서비스는 마지막 저장값만 읽고, API는 화면이 기존에 받던 묶음 모양을 유지한다.
        current = current_weather(self)
        types = {row["code"]: {"label": row["label"], "icon": row["icon"]}
                 for row in self.db.all("SELECT code, label, icon FROM weather_types ORDER BY code")}
        return {"current": current["code"], "types": types}

    def current_weather(self) -> dict:
        row = self.db.one(
            "SELECT c.code, t.label, t.icon FROM weather_current c "
            "JOIN weather_types t ON t.code=c.code WHERE c.id=1"
        )
        if row is None:
            raise RuntimeError("현재 날씨 데이터가 없습니다.")
        return {"code": row["code"], "label": row["label"], "icon": row["icon"]}

    def rules(self) -> dict:
        result = {}
        for row in self.db.all("SELECT key, value FROM recommendation_rules ORDER BY key"):
            result[row["key"]] = json.loads(row["value"]) if isinstance(row["value"], str) else row["value"]
        return result
