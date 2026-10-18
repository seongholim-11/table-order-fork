"""손님 API: 직원 호출. (담당: 석원)"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["사용자"])



class CallIn(BaseModel):
    table_no: int = Field(ge=1)
    items: list[str] = Field(min_length=1)


@router.get("/v1/staff-call-items")
async def staff_call_items(request: Request):
    """직원 호출 창의 선택 항목을 DB 정렬 순서대로 제공한다."""
    return request.app.state.shop.call_items()


@router.post("/v1/staff-calls", status_code=201)
@router.post("/calls", status_code=201)
async def create_call(body: CallIn, request: Request):
    """비회원도 사용할 수 있는 직원 호출을 DB에 저장한다."""
    call = request.app.state.shop.add_call(body.table_no, body.items)
    return {"id": call["id"]}
