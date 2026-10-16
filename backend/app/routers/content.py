"""손님 API: 화면용 콘텐츠(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙). 서준·석원·재현이 각자 항목을 새 엔드포인트로 옮긴다."""

from fastapi import APIRouter, HTTPException, Request

from app import dummy

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/content")
async def all_content(request: Request):
    """화면용 콘텐츠 전체(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙)를 한 번에 내려준다. [더미]"""
    return dummy.content()


@router.get("/content/{name}")
async def one_content(name: str, request: Request):
    data = dummy.content_item(name)  # [더미]
    if data is None:
        raise HTTPException(404, "없는 콘텐츠입니다.")
    return data
