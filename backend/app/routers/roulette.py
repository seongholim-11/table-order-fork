"""손님 API: 룰렛 당첨 기록과 쿠폰 발급. (담당: 재현)"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import dummy
from app.core.dependencies import current_member

router = APIRouter(prefix="/api", tags=["사용자"])



class PrizeIn(BaseModel):
    member_id: int
    prize: str = Field(min_length=1, max_length=50)
    # 아래를 함께 보내면 당첨 결과가 쿠폰함에 쿠폰으로 들어간다
    kind: str | None = Field(default=None, pattern="^(discount|free)$")
    emoji: str = Field(default="🎁", max_length=8)
    percent: int | None = Field(default=None, ge=1, le=100)
    item_id: str | None = Field(default=None, max_length=40)
    prize_id: int | None = None  # 당첨된 룰렛 칸 id(roulette_prizes.id). 화면이 아직 모르면 생략해도 된다


@router.put("/tables/{table_no}/logins/prize")
async def tablet_login_prize(table_no: int, body: PrizeIn, request: Request, member: dict = Depends(current_member)):
    """룰렛 당첨을 기록하고 쿠폰함에 쿠폰을 발급한다. [더미] 저장하지 않고 성공 응답만 돌려준다.

    TODO: 이 태블릿에 로그인한 회원인지 확인(tablet_rows, 아니면 404).
    TODO: 회원당 하루 1회(KST) 검사 coupons.issued_today(member_id) → 이미 돌렸으면 409.
    TODO: kind 가 있으면 할인은 percent, 서비스는 item_id 필수(아니면 422).
    TODO: login_id = tablet_logins.set_prize(table_no, member_id, prize, prize_id) 로 당첨 기록 → None 이면(이미 기록) 409.
    TODO: kind 가 있으면 coupons.issue(..., prize_id=prize_id, table_login_id=login_id) 로 쿠폰 발급.
    """
    return dummy.prize_saved(body.prize, body.kind, body.emoji, body.percent, body.item_id)
