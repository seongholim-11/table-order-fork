"""관리자: 대시보드 통계."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from app import dummy
from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services import stats as stats_service
from app.services.grades import KST

router = APIRouter()


@router.get("/stats")
async def dashboard(request: Request, settings: Settings = Depends(get_settings)):
    """[더미] 더미 주문·회원으로 통계를 계산한다."""
    d = dummy.dashboard_inputs()
    return stats_service.dashboard(d["orders"], d["members"], d["recommendations"],
                                   datetime.now(KST).date(), grade_rule(settings))
