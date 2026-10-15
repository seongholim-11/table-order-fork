"""사용자(손님) 페이지용 API."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.dependencies import current_member, optional_member
from app.core.settings import Settings, get_settings

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
async def store_info(settings: Settings = Depends(get_settings)):
    return {"name": settings.store_name, "branch": settings.store_branch, "slogan": settings.store_slogan,
            "tables": settings.store_tables}


@router.get("/content")
async def all_content(request: Request):
    """화면용 콘텐츠 전체(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙)를 한 번에 내려준다."""
    return request.app.state.content.all()


@router.get("/content/{name}")
async def one_content(name: str, request: Request):
    data = request.app.state.content.get(name)
    if data is None:
        raise HTTPException(404, "없는 콘텐츠입니다.")
    return data


@router.get("/menus")
async def list_menus(request: Request):
    """판매 중이든 품절이든 전부 돌려준다 (품절은 `soldout` 로 표시)."""
    return request.app.state.shop.menus()


@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, member: dict | None = Depends(optional_member)):
    order = request.app.state.shop.add_order(
        body.table_no, [l.model_dump(exclude_none=True) for l in body.lines], body.total, member["id"] if member else None)
    return {"no": order["id"], "ai_combo": order["ai_combo"]}


@router.post("/calls", status_code=201)
async def create_call(body: CallIn, request: Request):
    return {"id": request.app.state.shop.add_call(body.table_no, body.items)["id"]}


@router.post("/recommendations", status_code=201)
async def log_recommendation(body: RecommendationIn, request: Request, member: dict | None = Depends(optional_member)):
    """추천 조합이 손님에게 노출된 사실을 기록한다 (AI 추천 적중률의 분모)."""
    rid = request.app.state.shop.add_recommendation(body.table_no, member["id"] if member else None,
                                                    body.params, body.combo_ids)
    return {"id": rid}


@router.get("/members/me")
async def get_me(member: dict = Depends(current_member)):
    return _me(member)


@router.post("/members/me/opt-out")
async def opt_out(request: Request, member: dict = Depends(current_member)):
    return _me(request.app.state.members.opt_out(member["id"]))
