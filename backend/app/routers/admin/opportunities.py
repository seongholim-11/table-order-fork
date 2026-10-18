"""관리자 API: DB 근거로 만드는 AI 마케팅 추천 카드."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services import opportunities as opportunity_service
from app.services import growth_performance as growth_service
from app.services import stats as stats_service
from app.services.grades import KST
from app.stores.stats import StatsStore

router = APIRouter()


@router.get("/marketing/opportunities")
def opportunities(request: Request, round: int = Query(default=0, ge=0),
                  settings: Settings = Depends(get_settings)) -> dict:
    """같은 DB 입력이면 같은 카드가 나오며 round로 네 장씩 순환한다."""
    rule = grade_rule(settings, db=request.app.state.db)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    today = datetime.now(KST).date()
    store = StatsStore(request.app.state.db)
    orders, members = store.orders(), request.app.state.members.all()
    stats = stats_service.dashboard(orders, members, store.recommendation_count(), today, rule)
    return opportunity_service.opportunities(
        orders, members, request.app.state.shop.menus(), stats, today, rule, round)


@router.get("/marketing/growth-performance")
def growth_performance(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """orders·members DB에서 AI 도입 전후 성과를 같은 월환산 기준으로 계산한다."""
    rule = grade_rule(settings, db=request.app.state.db)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    return growth_service.calculate(StatsStore(request.app.state.db).orders(), request.app.state.members.all(),
                                    datetime.now(KST).date(), rule)
