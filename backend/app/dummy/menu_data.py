"""메뉴 더미 (손님 메뉴 목록·관리자 메뉴 목록·메뉴 저장). (담당: 서준)"""

from app.dummy._common import _json
from app.dummy.content_data import content

# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    # "GET /api/menus": "menus",
    "GET /admin/api/menus": "admin_menus",
    "PUT /admin/api/menus/{menu_id}": "menu_saved",
}


def menus() -> list[dict]:
    """메뉴 전체(품절 포함). 모양은 seed/menu.json 과 같다."""
    return _json("menu.json")


def admin_menus() -> dict:
    content_ = content()
    cats = [{"id": c["id"], "name": c["name"]} for c in content_["categories"] if c["id"] not in ("ai", "best")]
    return {"categories": cats, "menus": menus()}


def menu_saved(menu_id: str, fields: dict) -> dict:
    """저장된 메뉴 한 건. 더미 메뉴에 보낸 필드를 덮어쓴 모양이다 (없는 id 면 기본값으로 채운 새 메뉴)."""
    base = next((m for m in menus() if m["id"] == menu_id),
                {"id": menu_id, "cat": "side", "name": "새 메뉴", "desc": "", "price": 0, "emoji": "🍽️", "tags": [],
                 "soldout": False, "spicy": 0, "weight": 50, "set_ok": False, "image_url": ""})
    return {**base, **fields}
