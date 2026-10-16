"""관리자: 주문 이력."""

from fastapi import APIRouter, Request

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
