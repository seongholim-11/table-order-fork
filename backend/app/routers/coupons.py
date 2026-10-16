"""손님 API: 쿠폰함(내 쿠폰, 이 태블릿 로그인 회원들의 쿠폰). (담당: 재현)"""

from fastapi import APIRouter, Depends, Request

from app import dummy
from app.core.dependencies import current_member
from app.routers.user import tablet_rows

router = APIRouter(prefix="/api", tags=["사용자"])



@router.get("/v1/coupons")
@router.get("/coupons")
async def my_coupons(request: Request, member: dict = Depends(current_member)):
    """쿠폰함: 내 쿠폰 목록. 안 쓴 쿠폰이 먼저 나온다 (used_at 이 null 이면 사용 가능). [더미]"""
    return dummy.member_coupons(member["id"])


@router.get("/tables/{table_no}/coupons")
async def table_coupons(table_no: int, request: Request, member: dict = Depends(current_member)):
    """이 태블릿에 로그인한 회원들의 쿠폰함. 한 테이블에 여러 명이 앉으므로 화면의 쿠폰함 팝업이 이걸 쓴다."""
    tablet_rows(request, table_no, member)
    return dummy.table_coupons(table_no)  # [더미]
