"""사용자(손님) 페이지용 API."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.dependencies import current_member, optional_member
from app import dummy

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


class CallIn(BaseModel):
    table_no: int = Field(ge=1)
    items: list[str] = Field(min_length=1)


class RecommendationIn(BaseModel):
    table_no: int = Field(ge=1)
    params: dict = {}
    combo_ids: list[str] = []


def _me(m: dict) -> dict:
    return {"id": m["id"], "nickname": m["nickname"], "phone": m["phone"], "birth_year": m["birth_year"],
            "gender": m["gender"], "marketing_consent": bool(m["marketing_consent"]),
            "opted_out": bool(m["opted_out"]), "visit_count": m["visit_count"]}


@router.get("/store")
@router.get("/v1/store")  # 기획서(API 명세) 경로. 화면은 기존 /api/store 도 그대로 쓴다.
async def store_info(request: Request):
    """매장 정보(이름·지점 등) 조회. 스플래시·헤더에 매장명을 보여 줄 때 쓴다. [더미] app/dummy.py 의 값을 돌려준다."""
    return dummy.store()


@router.get("/content")
async def all_content(request: Request):
    """화면용 콘텐츠 전체(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙)를 한 번에 내려준다. [더미]"""
    return dummy.content()


@router.get("/content/{name}")
async def one_content(name: str, request: Request):
    data = dummy.content_item(name)  # [더미]
    if data is None:
        raise HTTPException(404, "없는 콘텐츠입니다.")
    return data


@router.get("/menus")
async def list_menus(request: Request):
    """판매 중이든 품절이든 전부 돌려준다 (품절은 `soldout` 로 표시). [더미]"""
    return dummy.menus()


@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, member: dict | None = Depends(optional_member)):
    """주문 생성. [더미] 저장하지 않고 성공 응답만 돌려준다.

    TODO: shop.add_order(table_no, lines, total, member_id) 로 주문·주문 줄 저장 (ai_combo: 줄 id 가 'combo:' 로 시작하면 True).
    TODO: 로그인 회원이면 이 태블릿 로그인 회원의 쿠폰만 coupons.use(coupon_ids, tablet_member_ids, order_id) 로 사용 처리.
    """
    return dummy.order_created(body.coupon_ids)


@router.post("/calls", status_code=201)
async def create_call(body: CallIn, request: Request):
    """직원 호출 등록. [더미] 저장하지 않는다. TODO: shop.add_call(table_no, items)."""
    return dummy.call_created()


@router.post("/recommendations", status_code=201)
async def log_recommendation(body: RecommendationIn, request: Request, member: dict | None = Depends(optional_member)):
    """추천 조합이 손님에게 노출된 사실을 기록한다 (AI 추천 적중률의 분모). [더미] 저장하지 않는다.

    TODO: shop.add_recommendation(table_no, member_id, params, combo_ids).
    """
    return dummy.recommendation_logged()


@router.get("/members/me")
async def get_me(member: dict = Depends(current_member)):
    return _me(member)


@router.post("/members/me/opt-out")
async def opt_out(request: Request, member: dict = Depends(current_member)):
    return _me(request.app.state.members.opt_out(member["id"]))


class PrizeIn(BaseModel):
    member_id: int
    prize: str = Field(min_length=1, max_length=50)
    # 아래를 함께 보내면 당첨 결과가 쿠폰함에 쿠폰으로 들어간다
    kind: str | None = Field(default=None, pattern="^(discount|free)$")
    emoji: str = Field(default="🎁", max_length=8)
    percent: int | None = Field(default=None, ge=1, le=100)
    item_id: str | None = Field(default=None, max_length=40)
    prize_id: int | None = None  # 당첨된 룰렛 칸 id(roulette_prizes.id). 화면이 아직 모르면 생략해도 된다


def _tablet_rows(request: Request, table_no: int, member: dict) -> list[dict]:
    """이 태블릿에 로그인한 회원만 그 태블릿의 기록을 볼 수 있다."""
    rows = request.app.state.tablet_logins.list(table_no)
    if all(r["id"] != member["id"] for r in rows):
        raise HTTPException(403, "이 태블릿에서 로그인한 회원이 아닙니다.")
    return rows


@router.get("/tables/{table_no}/logins")
async def tablet_logins(table_no: int, request: Request, member: dict = Depends(current_member)):
    """새로고침 후 '이 태블릿에서 로그인한 회원'(룰렛 사용 여부 포함)을 되살리기 위한 기록."""
    return _tablet_rows(request, table_no, member)


@router.put("/tables/{table_no}/logins/prize")
async def tablet_login_prize(table_no: int, body: PrizeIn, request: Request, member: dict = Depends(current_member)):
    """룰렛 당첨을 기록하고 쿠폰함에 쿠폰을 발급한다. [더미] 저장하지 않고 성공 응답만 돌려준다.

    TODO: 이 태블릿에 로그인한 회원인지 확인(_tablet_rows, 아니면 404).
    TODO: 회원당 하루 1회(KST) 검사 coupons.issued_today(member_id) → 이미 돌렸으면 409.
    TODO: kind 가 있으면 할인은 percent, 서비스는 item_id 필수(아니면 422).
    TODO: login_id = tablet_logins.set_prize(table_no, member_id, prize, prize_id) 로 당첨 기록 → None 이면(이미 기록) 409.
    TODO: kind 가 있으면 coupons.issue(..., prize_id=prize_id, table_login_id=login_id) 로 쿠폰 발급.
    """
    return dummy.prize_saved(body.prize, body.kind, body.emoji, body.percent, body.item_id)


@router.get("/v1/coupons")
@router.get("/coupons")
async def my_coupons(request: Request, member: dict = Depends(current_member)):
    """쿠폰함: 내 쿠폰 목록. 안 쓴 쿠폰이 먼저 나온다 (used_at 이 null 이면 사용 가능). [더미]"""
    return dummy.member_coupons(member["id"])


@router.get("/tables/{table_no}/coupons")
async def table_coupons(table_no: int, request: Request, member: dict = Depends(current_member)):
    """이 태블릿에 로그인한 회원들의 쿠폰함. 한 테이블에 여러 명이 앉으므로 화면의 쿠폰함 팝업이 이걸 쓴다."""
    _tablet_rows(request, table_no, member)
    return dummy.table_coupons(table_no)  # [더미]
