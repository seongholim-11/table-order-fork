"""추천 노출 기록 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다)."""

import json

SCHEMA = """\
CREATE TABLE IF NOT EXISTS recommendation_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no     INTEGER NOT NULL,
    member_id    INTEGER,
    answers      TEXT NOT NULL DEFAULT '{}',
    hour         INTEGER,
    weather_code TEXT,
    combo_ids    TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class RecommendationMixin:
    def add_recommendation(self, table_no: int, member_id: int | None, params: dict, combo_ids: list[str]) -> int:
        """추천 노출 1건을 저장하고 새 이벤트 id를 돌려준다."""
        # 답변 전체는 JSON으로 남기고, 통계에서 자주 쓰는 시간·날씨는 별도 칸에도 복사한다.
        answers = json.dumps(params, ensure_ascii=False)
        answers_value = "CAST(? AS jsonb)" if self.db.pg else "?"
        event_id = self.db.run(
            "INSERT INTO recommendation_events "
            "(table_no, member_id, answers, hour, weather_code, combo_ids) "
            f"VALUES (?, ?, {answers_value}, ?, ?, ?)",
            (table_no, member_id, answers, params.get("hour"), params.get("weather"), self.db.to_list(combo_ids)),
        )
        if event_id is None:
            raise RuntimeError("추천 노출 기록 id를 가져오지 못했습니다.")
        return event_id

    def recommendation_count(self) -> int:
        """추천 노출 총 횟수(관리자 AI 적중률의 분모)를 조회한다."""
        return int(self.db.one("SELECT COUNT(*) AS count FROM recommendation_events")["count"])
