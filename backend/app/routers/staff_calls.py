"""손님 API: 직원 호출. (담당: 석원)"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app import dummy

router = APIRouter(prefix="/api", tags=["사용자"])



class CallIn(BaseModel):
    table_no: int = Field(ge=1)
    items: list[str] = Field(min_length=1)


@router.post("/calls", status_code=201)
async def create_call(body: CallIn, request: Request):
    """직원 호출 등록. [더미] 저장하지 않는다. TODO: shop.add_call(table_no, items)."""
    return dummy.call_created()
