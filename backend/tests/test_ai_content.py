"""AI 질문·날씨·추천 규칙의 DB 응답과 화면 데이터 계약을 확인한다."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "user"))
import ai_quiz_data  # noqa: E402
import recommendation_data  # noqa: E402


def test_ai_content_endpoints_keep_frontend_shape(client):
    assert client.get("/api/v1/ai/questions").json() == ai_quiz_data.QUESTIONS
    assert client.get("/api/v1/weather/current").json() == ai_quiz_data.WEATHER
    assert client.get("/api/v1/ai/recommendation-rules").json() == recommendation_data.RULES


def test_ai_content_is_also_available_from_legacy_content_bundle(client):
    content = client.get("/api/content").json()
    assert content["quiz_questions"] == ai_quiz_data.QUESTIONS
    assert content["weather"] == ai_quiz_data.WEATHER
    assert content["rules"] == recommendation_data.RULES


def test_recommendation_event_is_saved_for_member_and_guest(client):
    shop = client.app.state.shop
    before = shop.recommendation_count()

    guest = client.post("/api/v1/ai/recommendations", json={
        "table_no": 1,
        "params": {"people": 2, "hour": 19, "weather": "rain"},
        "combo_ids": ["classic", "soup"],
    })
    assert guest.status_code == 201 and guest.json()["id"]
    saved = shop.db.one("SELECT * FROM recommendation_events WHERE id=?", (guest.json()["id"],))
    assert saved["member_id"] is None
    assert saved["hour"] == 19 and saved["weather_code"] == "rain"
    assert shop.db.from_list(saved["combo_ids"]) == ["classic", "soup"]

    assert shop.recommendation_count() == before + 1
