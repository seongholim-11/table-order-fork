"""관리자 API: 직원 호출 목록 조회와 처리 완료."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/calls")
async def list_calls(request: Request):
    """저장된 직원 호출을 최신순으로 조회한다."""
    return request.app.state.shop.list_calls()


@router.post("/calls/{call_id}/done")
async def mark_call_done(call_id: int, request: Request):
    """호출 한 건을 완료 처리하며, 같은 요청을 반복해도 같은 결과를 반환한다."""
    call = request.app.state.shop.mark_done(call_id)
    if call is None:
        raise HTTPException(404, "직원 호출을 찾을 수 없습니다.")
    return call
