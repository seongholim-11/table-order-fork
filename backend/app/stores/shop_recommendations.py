"""추천 기록 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다)."""

import json

from app.stores.members import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, table_no INTEGER NOT NULL, member_id INTEGER,
    answers TEXT NOT NULL DEFAULT '{}', hour INTEGER, weather_code TEXT, combo_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


class RecommendationMixin:
    def add_recommendation(self, table_no: int, member_id: int | None, params: dict, combo_ids: list[str]) -> int:
        return self.db.run(
            "INSERT INTO recommendation_events (table_no, member_id, answers, combo_ids, created_at) VALUES (?,?,?,?,?)",
            (table_no, member_id, json.dumps(params, ensure_ascii=False), self.db.to_list(combo_ids), now_iso()))

    def recommendation_count(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM recommendation_events")["n"]
