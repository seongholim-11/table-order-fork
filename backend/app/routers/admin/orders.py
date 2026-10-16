"""관리자: 주문 이력, 직원 호출."""

from fastapi import APIRouter, HTTPException, Request

from app import dummy

router = APIRouter()


@router.get("/orders")
async def list_orders(request: Request, member_id: int | None = None):
    """[더미] 주문 목록."""
    members = {m["id"]: m for m in dummy.members()}
    out = []
    for o in dummy.orders():
        if member_id is not None and o["member_id"] != member_id:
            continue
        m = members.get(o["member_id"])
        out.append({**o, "nickname": m["nickname"] if m else None})
    return out


@router.get("/calls")
async def list_calls():
    """[더미] 직원 호출 목록."""
    return dummy.calls()


@router.post("/calls/{call_id}/done")
async def finish_call(call_id: int, request: Request):
    """호출 처리 완료. [더미] 저장하지 않고 완료된 호출을 돌려준다. TODO: shop.finish_call(call_id), 없으면 404."""
    return dummy.call_finished(call_id)
