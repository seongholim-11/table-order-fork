"""손님 API: 메뉴 목록. (담당: 서준)"""

from fastapi import APIRouter, Request

from app import dummy

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/menus")
async def list_menus(request: Request):
    """판매 중이든 품절이든 전부 돌려준다 (품절은 `soldout` 로 표시). [더미]"""
    return dummy.menus()
