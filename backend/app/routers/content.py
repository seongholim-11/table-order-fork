"""손님 API: 화면용 콘텐츠(카테고리·AI 질문·날씨·추천 규칙). 모두 DB 저장소 값을 돌려준다."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/content")
def all_content(request: Request):
    """기존 화면용 묶음 경로. 카테고리·AI 질문·날씨·추천 규칙을 모두 DB 저장소에서 모아 돌려준다."""
    return {
        "categories": request.app.state.shop.categories.list(),  # 관리자가 바꾼 DB 값
        "quiz_questions": request.app.state.ai_content.questions(),
        "weather": request.app.state.ai_content.weather_shape(),
        "rules": request.app.state.ai_content.rules(),
    }


@router.get("/content/{name}")
def one_content(name: str, request: Request):
    if name == "quiz_questions":
        return request.app.state.ai_content.questions()
    if name == "weather":
        return request.app.state.ai_content.weather_shape()
    if name == "rules":
        return request.app.state.ai_content.rules()
    if name == "categories":
        return request.app.state.shop.categories.list()  # 관리자가 바꾼 DB 값
    # 위 네 가지 말고는 없는 콘텐츠다.
    raise HTTPException(404, "없는 콘텐츠입니다.")
