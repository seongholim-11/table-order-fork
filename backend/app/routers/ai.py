"""손님 API: AI 질문·추천 규칙·날씨와 추천 노출 기록."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.dependencies import optional_member
from app.core.settings import get_settings
from app.services.ai_recommendation import AiRecommendationUnavailable
from app.services.external_info import weather_type

router = APIRouter(prefix="/api", tags=["사용자"])



class RecommendationIn(BaseModel):
    table_no: int = Field(ge=1)
    params: dict = {}
    combo_ids: list[str] = []


class RecommendationGenerateIn(BaseModel):
    """제미나이 추천에 필요한 손님 답변과 현재 장바구니."""

    table_no: int = Field(ge=1)
    params: dict = Field(default_factory=dict)
    lines: list[dict] = Field(default_factory=list)


@router.get("/v1/ai/questions")
def questions(request: Request):
    """추천 질문과 선택지를 DB에서 화면용 모양으로 묶어 반환한다."""
    return request.app.state.ai_content.questions()


def real_weather_shape(request: Request) -> dict:
    """관리자 화면과 같은 날씨 API(Open-Meteo, 하루 한 번 저장)로 현재 날씨를 채운다.
    가져오지 못하면 DB에 저장된 날씨를 그대로 쓴다. 가져왔으면 `text`에 "맑은 18도 날씨" 문구를 함께 담는다."""
    shape = request.app.state.ai_content.weather_shape()
    text = request.app.state.external.today_weather()
    code = weather_type(text)
    if code in shape["types"]:
        return {**shape, "current": code, "text": text}
    return shape


@router.get("/v1/weather/current")
def current_weather(request: Request):
    """오늘 날씨(날씨 API). 날씨 API가 실패하면 DB에 저장된 마지막 날씨를 반환한다."""
    return real_weather_shape(request)


@router.get("/v1/ai/recommendation-rules")
def recommendation_rules(request: Request):
    """추천 화면이 사용하는 규칙 JSON을 DB에서 반환한다."""
    return request.app.state.ai_content.rules()


@router.post("/v1/ai/recommendations/generate")
def generate_recommendations(
    body: RecommendationGenerateIn,
    request: Request,
    member: dict | None = Depends(optional_member),
):
    """DB 메뉴·주문·추천 규칙을 제미나이에 분석시켜 검증된 조합을 돌려준다."""
    # 현재 테이블의 로그인 이후 주문은 서버 DB에서 직접 읽어 모델의 근거로 사용한다.
    since = request.app.state.tablet_logins.first_valid_login_at(body.table_no)
    table_orders = request.app.state.shop.table_orders(body.table_no, since)
    history_lines = [line for order in table_orders for line in order["lines"]]
    # 답변에 날씨가 없으면(AI 추천 조합 화면) 오늘 실제 날씨를 근거로 쓴다
    params = {"weather": real_weather_shape(request)["current"], **body.params}
    try:
        return request.app.state.ai_recommendation.generate(
            params,
            [*body.lines, *history_lines],
            member=bool(member),
        )
    except AiRecommendationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/v1/ai/recommendations", status_code=201)
@router.post("/recommendations", status_code=201)
def log_recommendation(body: RecommendationIn, request: Request, member: dict | None = Depends(optional_member)):
    """추천 조합이 손님에게 노출된 사실을 기록한다 (AI 추천 적중률의 분모)."""
    event_id = request.app.state.shop.add_recommendation(
        body.table_no, member["id"] if member else None, body.params, body.combo_ids
    )
    return {"id": event_id}
