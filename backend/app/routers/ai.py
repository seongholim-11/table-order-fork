"""손님 API: AI 추천 기록(추천 질문·규칙·날씨는 여기에 새로 만든다). (담당: 재현)"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import dummy
from app.core.dependencies import optional_member

router = APIRouter(prefix="/api", tags=["사용자"])



class RecommendationIn(BaseModel):
    table_no: int = Field(ge=1)
    params: dict = {}
    combo_ids: list[str] = []


@router.post("/recommendations", status_code=201)
async def log_recommendation(body: RecommendationIn, request: Request, member: dict | None = Depends(optional_member)):
    """추천 조합이 손님에게 노출된 사실을 기록한다 (AI 추천 적중률의 분모). [더미] 저장하지 않는다.

    TODO: shop.add_recommendation(table_no, member_id, params, combo_ids).
    """
    return dummy.recommendation_logged()
