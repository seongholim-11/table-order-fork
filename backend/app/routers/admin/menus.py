"""관리자: 메뉴 관리."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


def menu_categories(request: Request) -> list[dict]:
    """메뉴를 넣을 수 있는 카테고리를 저장소에서 가져온다."""
    return request.app.state.shop.menu_categories()


class MenuIn(BaseModel):
    id: str | None = None
    delete: bool | None = None
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
async def menus(request: Request):
    """관리자 화면에 필요한 카테고리와 메뉴 목록을 돌려준다."""
    return {"categories": menu_categories(request), "menus": request.app.state.shop.menus()}


@router.put("/menus/{menu_id}")
async def save_menu(menu_id: str, body: MenuIn | list[MenuIn], request: Request):
    """한 메뉴 또는 여러 메뉴를 기존 PUT 경로에서 검증한 뒤 저장한다."""
    shop = request.app.state.shop
    categories = {category["id"] for category in menu_categories(request)}

    if isinstance(body, list):
        # 목록의 첫 ID를 URL에 적어 기존 메뉴 PUT 경로를 그대로 사용한다.
        if not body:
            raise HTTPException(422, "저장할 메뉴를 한 개 이상 보내 주세요.")
        items = [item.model_dump(exclude_unset=True, exclude_none=True) for item in body]
        ids = [item.get("id") for item in items]
        if any(not isinstance(menu_id_in_body, str) or not menu_id_in_body.strip() for menu_id_in_body in ids):
            raise HTTPException(422, "일괄 저장할 각 메뉴에 ID를 입력해 주세요.")
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "일괄 저장 요청에 같은 메뉴 ID가 중복되었습니다.")
        if ids[0] != menu_id:
            raise HTTPException(422, "URL의 메뉴 ID는 목록 첫 번째 메뉴 ID와 같아야 합니다.")
        for item in items:
            if item.get("delete") is True:
                if set(item) - {"id", "delete"}:
                    raise HTTPException(422, "삭제 항목에는 ID와 delete만 보낼 수 있습니다.")
                if shop.menu(item["id"]) is None:
                    raise HTTPException(404, f"메뉴를 찾을 수 없습니다: {item['id']}")
            else:
                item.pop("delete", None)
                _validate_menu_fields(shop, item["id"], item, categories)
        return shop.save_menu(menu_id, items)

    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if fields.get("id") not in (None, menu_id):
        raise HTTPException(422, "요청 메뉴 ID와 URL의 메뉴 ID가 다릅니다.")
    fields.pop("id", None)
    if fields.pop("delete", False):
        raise HTTPException(422, "단건 삭제는 DELETE 메뉴 경로를 사용해 주세요.")
    _validate_menu_fields(shop, menu_id, fields, categories)
    return shop.save_menu(menu_id, fields)


def _validate_menu_fields(shop, menu_id: str, fields: dict, categories: set[str]) -> None:
    """한 메뉴씩 저장 조건을 확인해 일괄 요청에서 부분 저장이 일어나지 않게 한다."""
    existing = shop.menu(menu_id)
    if existing is None:
        required = ("name", "cat", "price")
        missing = [field for field in required if field not in fields]
        if missing:
            labels = {"name": "메뉴 이름", "cat": "카테고리", "price": "가격"}
            missing_labels = ", ".join(labels[field] for field in missing)
            raise HTTPException(422, f"새 메뉴 등록에 필요한 항목을 입력해 주세요: {missing_labels}.")
    if "cat" in fields and fields["cat"] not in categories:
        raise HTTPException(422, "존재하지 않는 메뉴 카테고리입니다.")


@router.delete("/menus/{menu_id}", status_code=204)
async def delete_menu(menu_id: str, request: Request):
    """메뉴를 삭제하고, 없는 메뉴면 404를 돌려준다."""
    if not request.app.state.shop.delete_menu(menu_id):
        raise HTTPException(404, "메뉴를 찾을 수 없습니다.")
    return None
