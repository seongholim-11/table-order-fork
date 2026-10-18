"""관리자 API: 외부 정보(날씨·행사) (성호)."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/marketing/external-context")
def external_context(request: Request):
    """오늘(KST) 날씨·행사 문구. 저장된 값이 있으면 그대로, 없으면 외부 API로 채워 저장한다."""
    return request.app.state.external.today()
