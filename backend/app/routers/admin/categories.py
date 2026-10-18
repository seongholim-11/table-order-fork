"""관리자 카테고리 CRUD와 손님용 카테고리 목록 API."""

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.stores.categories import CategoryError
API_PREFIX = "/api"

router = APIRouter()
guest_router = APIRouter(prefix=API_PREFIX, tags=["사용자"])


class CategoryIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=80)
    icon: str = Field(default="🍽️", max_length=20)
    colors: list[str] = Field(default_factory=lambda: ["#a29bfe", "#4b3f9e"], min_length=2, max_length=2)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    icon: str | None = Field(default=None, max_length=20)
    colors: list[str] | None = Field(default=None, min_length=2, max_length=2)


def _category_error(error: CategoryError) -> HTTPException:
    """이름 오류와 카테고리 사용 제약을 알맞은 HTTP 오류로 바꾼다."""
    status = 422 if "이름을 입력" in str(error) else 409
    return HTTPException(status, str(error))


@router.get("/categories")
async def admin_categories(request: Request):
    """관리자 카테고리 목록에는 메뉴 개수를 포함한다."""
    return request.app.state.shop.categories.list(include_count=True)


@router.post("/categories", status_code=201)
async def add_category(body: CategoryIn, request: Request):
    """새 카테고리를 표시 순서의 마지막에 추가한다."""
    category_id = body.id or f"cat{uuid.uuid4().hex[:8]}"
    try:
        return request.app.state.shop.categories.add(category_id, body.name, body.icon, body.colors)
    except CategoryError as error:
        raise _category_error(error) from error


@router.patch("/categories/{category_id}")
async def update_category(category_id: str, body: CategoryPatch, request: Request):
    """요청에 포함된 카테고리 항목만 수정한다."""
    try:
        category = request.app.state.shop.categories.update(
            category_id, body.model_dump(exclude_unset=True, exclude_none=True)
        )
    except CategoryError as error:
        raise _category_error(error) from error
    if category is None:
        raise HTTPException(404, "카테고리를 찾을 수 없습니다.")
    return category


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(category_id: str, request: Request):
    """메뉴가 연결된 카테고리는 삭제하지 않고 409로 안내한다."""
    try:
        exists, menu_count = request.app.state.shop.categories.delete(category_id)
    except CategoryError as error:
        raise _category_error(error) from error
    if not exists:
        raise HTTPException(404, "카테고리를 찾을 수 없습니다.")
    if menu_count:
        raise HTTPException(409, f"메뉴 {menu_count}개가 남아 있어요. 메뉴를 먼저 옮기거나 삭제해 주세요.")
    return None


@guest_router.get("/categories")
async def guest_categories(request: Request):
    """손님 주문 화면에 필요한 카테고리를 같은 테이블에서 읽어 준다."""
    return request.app.state.shop.categories.list()
