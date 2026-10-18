"""손님 API: 매장 정보. (담당: 재현)"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/store")
@router.get("/v1/store")  # 기획서(API 명세) 경로. 화면은 기존 /api/store 도 그대로 쓴다.
async def store_info(request: Request):
    """DB에 저장된 매장 정보를 스플래시·헤더에 전달한다."""
    # 앱 시작 때 만들어 둔 저장소를 사용해 매장 정보 한 행을 조회한다.
    return request.app.state.store_info.get()
