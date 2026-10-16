"""손님 API: 매장 정보. (담당: 재현)"""

from fastapi import APIRouter, Request

from app import dummy

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/store")
@router.get("/v1/store")  # 기획서(API 명세) 경로. 화면은 기존 /api/store 도 그대로 쓴다.
async def store_info(request: Request):
    """매장 정보(이름·지점 등) 조회. 스플래시·헤더에 매장명을 보여 줄 때 쓴다. [더미] app/dummy 의 값을 돌려준다."""
    return dummy.store()
