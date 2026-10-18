"""관리자: 주문 이력."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/orders")
async def list_orders(request: Request, member_id: int | None = None):
    """실제 주문과 회원 닉네임을 최신순으로 조회한다."""
    return request.app.state.shop.orders(member_id)
