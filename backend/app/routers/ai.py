"""손님 API: AI 질문·추천 규칙·날씨와 추천 노출 기록."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.dependencies import optional_member

router = APIRouter(prefix="/api", tags=["사용자"])



class RecommendationIn(BaseModel):
    table_no: int = Field(ge=1)
    params: dict = {}
    combo_ids: list[str] = []


@router.get("/v1/ai/questions")
async def questions(request: Request):
    """추천 질문과 선택지를 DB에서 화면용 모양으로 묶어 반환한다."""
    return request.app.state.ai_content.questions()


@router.get("/v1/weather/current")
async def current_weather(request: Request):
    """외부 API 연동 전까지 DB에 저장된 마지막 날씨를 반환한다."""
    return request.app.state.ai_content.weather_shape()


@router.get("/v1/ai/recommendation-rules")
async def recommendation_rules(request: Request):
    """추천 화면이 사용하는 규칙 JSON을 DB에서 반환한다."""
    return request.app.state.ai_content.rules()


@router.post("/v1/ai/recommendations", status_code=201)
@router.post("/recommendations", status_code=201)
async def log_recommendation(body: RecommendationIn, request: Request, member: dict | None = Depends(optional_member)):
    """추천 조합이 손님에게 노출된 사실을 기록한다 (AI 추천 적중률의 분모)."""
    event_id = request.app.state.shop.add_recommendation(
        body.table_no, member["id"] if member else None, body.params, body.combo_ids
    )
    return {"id": event_id}
