"""메뉴 더미 (손님 메뉴 목록·관리자 메뉴 목록·메뉴 저장). (담당: 서준)"""

from app.dummy._common import _json

# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    # "GET /api/menus": "menus",
}


def menus() -> list[dict]:
    """메뉴 전체(품절 포함). 모양은 seed/menu.json 과 같다."""
    return _json("menu.json")
