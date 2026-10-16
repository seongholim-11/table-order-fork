"""관리자: 메뉴 관리."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import dummy

router = APIRouter()

NON_MENU_CATEGORIES = {"ai", "best"}  # 화면용 가상 카테고리(AI 추천 조합·인기메뉴)에는 메뉴를 직접 넣지 않는다


def menu_categories(request: Request) -> list[dict]:
    """메뉴를 넣을 수 있는 카테고리. 손님 화면의 카테고리 콘텐츠에서 가져온다."""
    return [{"id": c["id"], "name": c["name"]} for c in request.app.state.content.get("categories")
            if c["id"] not in NON_MENU_CATEGORIES]


class MenuIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    cat: str | None = None
    price: int | None = Field(default=None, ge=0)
    desc: str | None = None
    image_url: str | None = None
    soldout: bool | None = None
    spicy: int | None = Field(default=None, ge=0, le=3)
    weight: int | None = Field(default=None, ge=0, le=100)  # OWNER 추천 가중치
    set_ok: bool | None = None
    emoji: str | None = None
    tags: list[str] | None = None


@router.get("/menus")
async def menus():
    """[더미] 메뉴 목록과 카테고리."""
    return dummy.admin_menus()


@router.put("/menus/{menu_id}")
async def save_menu(menu_id: str, body: MenuIn, request: Request):
    """없는 id 면 새 메뉴를 만든다(이름·카테고리·가격 필수), 있으면 보낸 필드만 수정한다."""
    shop = request.app.state.shop
    fields = body.model_dump(exclude_none=True)
    if "cat" in fields and fields["cat"] not in {c["id"] for c in menu_categories(request)}:
        raise HTTPException(422, "알 수 없는 카테고리입니다.")
    if not shop.menu(menu_id) and not {"name", "cat", "price"} <= fields.keys():
        raise HTTPException(422, "새 메뉴는 name, cat, price 가 필요합니다.")
    return shop.save_menu(menu_id, fields)


@router.delete("/menus/{menu_id}", status_code=204)
async def delete_menu(menu_id: str, request: Request):
    if not request.app.state.shop.delete_menu(menu_id):
        raise HTTPException(404, "없는 메뉴입니다.")
