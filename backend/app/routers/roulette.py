"""손님 API: 룰렛 당첨 기록과 쿠폰 발급. (담당: 재현)"""

import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.dependencies import current_member
from app.routers.user import tablet_rows

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


class PlayIn(BaseModel):
    table_no: int = Field(ge=1)
    member_id: int | None = None


def _validate_prize(body: PrizeIn, request: Request) -> None:
    """쿠폰 종류별 필수값을 확인해 잘못된 쿠폰이 DB에 들어가지 않게 한다."""
    if body.kind == "discount" and body.percent is None:
        raise HTTPException(422, "할인 쿠폰에는 percent가 필요합니다.")
    if body.kind == "free":
        if not body.item_id:
            raise HTTPException(422, "서비스 쿠폰에는 item_id가 필요합니다.")
        if not request.app.state.roulette_prizes.service_menu_exists(body.item_id):
            raise HTTPException(422, "서비스 쿠폰 메뉴를 찾을 수 없습니다.")


def _save_prize(table_no: int, body: PrizeIn, request: Request) -> dict:
    """룰렛 결과 기록과 쿠폰 발급을 한 흐름으로 묶어 PUT·POST가 같은 규칙을 쓴다."""
    rows = request.app.state.tablet_logins.list(table_no)
    if not any(row["id"] == body.member_id for row in rows):
        raise HTTPException(404, "이 태블릿에서 로그인한 회원이 아닙니다.")
    _validate_prize(body, request)
    if request.app.state.coupons.issued_today(body.member_id):
        raise HTTPException(409, "오늘은 이미 룰렛을 돌렸습니다.")

    login_id = request.app.state.tablet_logins.set_prize(table_no, body.member_id, body.prize, body.prize_id)
    if login_id is None:
        raise HTTPException(409, "이미 룰렛을 처리했거나 참여할 수 없습니다.")

    coupon = None
    if body.kind:
        coupon = request.app.state.coupons.issue(
            body.member_id, table_no, body.kind, body.prize, body.emoji, body.percent, body.item_id,
            prize_id=body.prize_id, table_login_id=login_id,
        )
    return {"ok": True, "coupon": coupon}


@router.put("/tables/{table_no}/logins/prize")
async def tablet_login_prize(table_no: int, body: PrizeIn, request: Request,
                             member: dict = Depends(current_member)):
    """룰렛 당첨을 기록하고 쿠폰을 발급한다."""
    tablet_rows(request, table_no, member)
    return _save_prize(table_no, body, request)


@router.get("/v1/roulette/status")
async def roulette_status(request: Request, table_no: int = Query(ge=1),
                          member: dict = Depends(current_member)):
    """이 태블릿의 회원별 룰렛 상태와 남은 기회를 반환한다."""
    rows = tablet_rows(request, table_no, member)
    left = sum(1 for row in rows if row["eligible"] and row["prize"] is None)
    return {"members": rows, "spins_left": left, "remaining": left}


@router.post("/v1/roulette/plays", status_code=201)
async def play_roulette(body: PlayIn, request: Request, member: dict = Depends(current_member)):
    """가중치에 따라 서버가 룰렛 칸을 정하고, 당첨 기록과 쿠폰을 저장한다."""
    rows = tablet_rows(request, body.table_no, member)
    target_id = body.member_id if body.member_id is not None else member["id"]
    target = next((row for row in rows if row["id"] == target_id), None)
    if not target:
        raise HTTPException(404, "이 태블릿에서 로그인한 회원이 아닙니다.")
    if not target["eligible"] or target["prize"] is not None or request.app.state.coupons.issued_today(target_id):
        raise HTTPException(409, "오늘은 이미 룰렛을 돌렸습니다.")

    prizes = request.app.state.roulette_prizes.list()
    if not prizes:
        raise HTTPException(503, "룰렛 칸이 설정되지 않았습니다.")
    weights = [max(float(prize.get("weight", 1)), 0) for prize in prizes]
    index = random.randrange(len(prizes)) if not sum(weights) else random.choices(range(len(prizes)), weights=weights, k=1)[0]
    prize = prizes[index]
    saved = _save_prize(
        body.table_no,
        PrizeIn(member_id=target_id, prize=prize["short"], kind=prize["kind"], emoji=prize.get("emoji", "🎁"),
                percent=prize.get("percent"), item_id=prize.get("item_id")),
        request,
    )
    return {"index": index, "prize": prize, "coupon": saved["coupon"]}
