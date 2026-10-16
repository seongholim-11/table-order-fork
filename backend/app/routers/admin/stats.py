"""관리자: 대시보드 통계."""

from fastapi import APIRouter, Request

from app import dummy

router = APIRouter()


@router.get("/stats")
async def dashboard(request: Request):
    """[더미] 고정 통계 값. 실제 구현은 아래 TODO.

    TODO: 주문·회원·추천 노출 수를 DB 에서 읽어 services.stats.dashboard(orders, members, recommendations, today, rule) 로
          계산한다. rule 은 routers.admin.common.grade_rule(settings), today 는 datetime.now(KST).date().
    """
    return dummy.dashboard_stats()
