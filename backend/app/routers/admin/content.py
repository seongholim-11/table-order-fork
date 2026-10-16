"""관리자: 화면용 콘텐츠(카테고리·룰렛·직원 호출 항목 등) 교체."""

from fastapi import APIRouter, Body, Request

from app import dummy

router = APIRouter()


@router.put("/content/{name}")
async def save_content(name: str, request: Request, data: dict | list = Body(...)):
    """콘텐츠를 통째로 교체한다. [더미] 저장하지 않고 받은 값을 그대로 돌려준다.

    TODO: name 이 알려진 콘텐츠(categories, roulette_prizes, staff_calls ...)인지 확인하고 아니면 404.
    TODO: 새 스키마(db/fbgrowth_schema.sql)의 해당 테이블(categories, roulette_prizes, staff_call_items 등)에 통째로 교체 저장한다.
    TODO: 기존과 같은 종류(목록/객체)이고 비어 있지 않아야 한다(아니면 422).
    TODO: name == "roulette_prizes" 면 칸 2~8개, 칸마다 label·short·kind(discount|free) 필수,
          할인 칸 percent 1~100, 서비스 칸 item_id 필수, weight 는 0 이상이며 합이 0보다 커야 한다(아니면 422).
    """
    return dummy.content_saved(data)
