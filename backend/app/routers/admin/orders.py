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
    call = request.app.state.shop.finish_call(call_id)
    if not call:
        raise HTTPException(404, "없는 호출입니다.")
    return call
