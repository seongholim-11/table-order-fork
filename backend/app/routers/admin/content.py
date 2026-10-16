"""관리자: 화면용 콘텐츠(카테고리·룰렛·직원 호출 항목 등) 교체."""

from fastapi import APIRouter, Body, Request

from app import dummy

router = APIRouter()


@router.put("/content/{name}")
async def save_content(name: str, request: Request, data: dict | list = Body(...)):
    """콘텐츠를 통째로 교체한다. [더미] 저장하지 않고 받은 값을 그대로 돌려준다.

    TODO: store = request.app.state.content; current = store.get(name) 이 None 이면 404.
    TODO: 기존과 같은 종류(목록/객체)이고 비어 있지 않아야 한다(아니면 422).
    TODO: name == "roulette_prizes" 면 칸 2~8개, 칸마다 label·short·kind(discount|free) 필수,
          할인 칸 percent 1~100, 서비스 칸 item_id 필수, weight 는 0 이상이며 합이 0보다 커야 한다(아니면 422).
    TODO: store.set(name, data) 로 저장.
    """
    return dummy.content_saved(data)
