"""DB 자료를 제미나이에 전달하고 안전한 조합으로 되돌리는지 확인한다."""

from app.services.ai_recommendation import AiRecommendationService
from tests.conftest import settings
from fastapi.testclient import TestClient

from app.factory import create_app


def test_gemini_recommendation_uses_db_menu_data_and_recalculates_price(monkeypatch):
    def fake(self, prompt):
        assert '"menus"' in prompt and '"pairings"' in prompt
        return {"recommendations": [{"combo_id": "classic", "reason": "치킨과 감자튀김이 잘 어울려요."}]}

    monkeypatch.setattr(AiRecommendationService, "_ask_gemini", fake)
    with TestClient(create_app(settings(gemini_api_key="test-key"))) as client:
        response = client.post("/api/v1/ai/recommendations/generate", json={
            "table_no": 1,
            "params": {"people": 2, "budget": 40000, "spicy": "상관없어요", "drink": "맥주"},
            "lines": [],
        })

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "gemini"
    combo = body["combos"][0]
    assert combo["id"] == "classic"
    assert combo["price"] == combo["original"] - combo["discount"]
    assert all(component["unit"] >= 0 for component in combo["components"])


def test_gemini_recommendation_requires_api_key(client):
    response = client.post("/api/v1/ai/recommendations/generate", json={
        "table_no": 1,
        "params": {"people": 2, "budget": 40000, "spicy": "상관없어요", "drink": "맥주"},
    })
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
