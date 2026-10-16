"""추천 기록 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). [뼈대] 시그니처와 스키마만 남겼다."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, table_no INTEGER NOT NULL, member_id INTEGER,
    answers TEXT NOT NULL DEFAULT '{}', hour INTEGER, weather_code TEXT, combo_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


class RecommendationMixin:
    def add_recommendation(self, table_no: int, member_id: int | None, params: dict, combo_ids: list[str]) -> int:
        """TODO: recommendation_events 에 INSERT (params 는 JSON 문자열, combo_ids 는 db.to_list), 새 id 반환."""
        raise NotImplementedError

    def recommendation_count(self) -> int:
        """TODO: 추천 노출 총 횟수 (AI 적중률 분모)."""
        raise NotImplementedError
