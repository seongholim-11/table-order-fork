"""손님 API: 화면용 콘텐츠(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙). 서준·석원·재현이 각자 항목을 새 엔드포인트로 옮긴다."""

from fastapi import APIRouter, HTTPException, Request

from app import dummy

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/content")
async def all_content(request: Request):
    """기존 화면용 묶음 경로를 유지하되 AI 항목은 새 DB 저장소에서 합친다."""
    data = dummy.content()
    data["quiz_questions"] = request.app.state.ai_content.questions()
    data["weather"] = request.app.state.ai_content.weather_shape()
    data["rules"] = request.app.state.ai_content.rules()
    return data


@router.get("/content/{name}")
async def one_content(name: str, request: Request):
    if name == "quiz_questions":
        return request.app.state.ai_content.questions()
    if name == "weather":
        return request.app.state.ai_content.weather_shape()
    if name == "rules":
        return request.app.state.ai_content.rules()
    data = dummy.content_item(name)  # [더미]
    if data is None:
        raise HTTPException(404, "없는 콘텐츠입니다.")
    return data
