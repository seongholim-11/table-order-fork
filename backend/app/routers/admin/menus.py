"""관리자: 메뉴 관리."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app import dummy

router = APIRouter()

NON_MENU_CATEGORIES = {"ai", "best"}  # 화면용 가상 카테고리(AI 추천 조합·인기메뉴)에는 메뉴를 직접 넣지 않는다


def menu_categories(request: Request) -> list[dict]:
    """메뉴를 넣을 수 있는 카테고리 (ai·best 제외). [더미] 더미 콘텐츠에서 가져온다.

    TODO: categories 테이블(db/fbgrowth_schema.sql)에서 카테고리를 읽는다.
    """
    return [{"id": c["id"], "name": c["name"]} for c in dummy.content_item("categories")
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
    """메뉴 등록·수정(가중치·품절 포함). [더미] 저장하지 않고 보낸 값을 반영한 메뉴를 돌려준다.

    TODO: cat 이 menu_categories() 에 없으면 422.
    TODO: 없는 id 면 새로 만들고(name·cat·price 필수, 아니면 422), 있으면 보낸 필드만 수정: shop.save_menu(menu_id, fields).
    """
    return dummy.menu_saved(menu_id, body.model_dump(exclude_none=True))


@router.delete("/menus/{menu_id}", status_code=204)
async def delete_menu(menu_id: str, request: Request):
    """메뉴 삭제. [더미] 아무것도 지우지 않는다. TODO: shop.delete_menu(menu_id), 없으면 404."""
