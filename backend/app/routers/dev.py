"""포크·DB 연결을 확인하는 개발 전용 API."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.settings import Settings, get_settings

router = APIRouter(prefix="/api/dev", tags=["개발"])


@router.post("/db-test")
async def db_test(request: Request, settings: Settings = Depends(get_settings)):
    # 실수로 운영에서 노출되지 않도록 설정을 켜지 않은 서버에는 경로 자체가 없는 것처럼 응답한다.
    if not settings.dev_test_button:
        raise HTTPException(status_code=404, detail="Not Found")
    return request.app.state.dev_test.write_and_read()
