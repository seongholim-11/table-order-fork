"""손님 API: 주문 생성(쿠폰 사용 포함)과 테이블 누적 주문. (담당: 재현)"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import dummy
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
async def create_order(body: OrderIn, request: Request, member: dict | None = Depends(optional_member)):
    """주문 생성. [더미] 저장하지 않고 성공 응답만 돌려준다.

    TODO: shop.add_order(table_no, lines, total, member_id) 로 주문·주문 줄 저장 (ai_combo: 줄 id 가 'combo:' 로 시작하면 True).
    TODO: 로그인 회원이면 이 태블릿 로그인 회원의 쿠폰만 coupons.use(coupon_ids, tablet_member_ids, order_id) 로 사용 처리.
    """
    return dummy.order_created(body.coupon_ids)
