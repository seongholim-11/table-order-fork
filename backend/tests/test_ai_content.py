"""AI 질문·날씨·추천 규칙의 DB 응답과 화면 데이터 계약을 확인한다."""

import sys
from pathlib import Path

import pytest

from app.services.external_info import ExternalInfoService, weather_type

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "user"))
import ai_quiz_data  # noqa: E402
import recommendation_data  # noqa: E402


@pytest.fixture(autouse=True)
def no_real_weather(monkeypatch):
    """테스트가 실제 날씨 API를 부르지 않게 막는다(실패 상황 = DB에 저장된 더미 날씨를 쓴다)."""
    monkeypatch.setattr(ExternalInfoService, "fetch_weather", lambda self: "")


def test_weather_type_maps_text_to_code():
    assert weather_type("맑은 18도 날씨") == "sunny"
    assert weather_type("비 오는 18도 날씨") == "rain"
    assert weather_type("이슬비 오는 10도 날씨") == "rain"
    assert weather_type("눈 오는 -2도 날씨") == "snow"
    assert weather_type("흐린 15도 날씨") == "cloudy"
    assert weather_type("맑은 31도 날씨") == "hot"
    assert weather_type("") is None


def test_current_weather_uses_weather_api_text(client, monkeypatch):
    monkeypatch.setattr(ExternalInfoService, "fetch_weather", lambda self: "비 오는 18도 날씨")
    body = client.get("/api/v1/weather/current").json()
    assert body["current"] == "rain" and body["text"] == "비 오는 18도 날씨"
    assert body["types"] == ai_quiz_data.WEATHER["types"]


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
