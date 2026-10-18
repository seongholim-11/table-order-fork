"""손님 API: 주문 생성(쿠폰 사용 포함)과 테이블 누적 주문. (담당: 재현)"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.dependencies import optional_member

router = APIRouter(prefix="/api", tags=["사용자"])



class OrderLine(BaseModel):
    id: str
    name: str
    opt: str = ""
    unit: int = Field(ge=0)
    qty: int = Field(ge=1, le=99)
    components: list[dict] | None = None
    original_unit: int | None = None


class OrderIn(BaseModel):
    table_no: int = Field(ge=1)
    lines: list[OrderLine] = Field(min_length=1)
    total: int = Field(ge=0)
    coupon_ids: list[int] = []  # 이 주문에 쓴 쿠폰 (쿠폰함에서 '사용'한 것)


@router.post("/orders", status_code=201)
@router.post("/v1/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, member: dict | None = Depends(optional_member)):
    """주문 생성. 주문 본체와 주문 줄을 저장하고 화면이 쓰는 응답을 돌려준다.

    쿠폰의 실제 사용 처리는 3-4에서 같은 주문 id에 연결한다.
    """
    saved = request.app.state.shop.add_order(body.table_no, [line.model_dump() for line in body.lines], body.total,
                                              member["id"] if member else None)
    used_coupon_ids = []
    if member and body.coupon_ids:
        # 한 테이블의 로그인 회원들이 공유하는 쿠폰함에서만 사용 처리한다.
        table_members = request.app.state.tablet_logins.list(body.table_no)
        used_coupon_ids = request.app.state.coupons.use(
            body.coupon_ids, [row["id"] for row in table_members], saved["id"])
    return {"no": saved["id"], "ai_combo": saved["ai_combo"], "used_coupon_ids": used_coupon_ids}


@router.get("/v1/tables/{table_no}/orders")
async def table_orders(table_no: int, request: Request):
    """현재 유효한 테이블 로그인 이후의 주문과 누적 금액을 돌려준다."""
    since = request.app.state.tablet_logins.first_valid_login_at(table_no)
    rows = request.app.state.shop.table_orders(table_no, since)
    return {"orders": rows, "total": sum(row["total"] for row in rows)}
