"""관리자: 대시보드 통계."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services import stats as stats_service
from app.services.grades import KST
from app.stores.stats import StatsStore

router = APIRouter()


def dashboard(request: Request, settings: Settings = Depends(get_settings),
              repeat: int | None = Query(default=None, ge=2),
              regular: int | None = Query(default=None, ge=3),
              dormant: int | None = Query(default=None, ge=1)) -> dict:
    """조회 기준만 바꿔 계산하며 회원 기록이나 서버 설정은 저장하지 않는다."""
    rule = grade_rule(settings, repeat, regular, dormant, db=request.app.state.db)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    store = StatsStore(request.app.state.db)
    return stats_service.dashboard(store.orders(), request.app.state.members.all(),
                                   store.recommendation_count(), datetime.now(KST).date(), rule)


# 각 세부 API는 같은 의존 함수로 집계해 계산 규칙이 서로 달라지지 않게 한다.
@router.get("/stats")
def all_stats(result: dict = Depends(dashboard)):
    return result


@router.get("/stats/sales")
def sales(result: dict = Depends(dashboard)):
    return {key: result[key] for key in ("today_orders", "avg_order_amount")}


@router.get("/stats/menus/ranking")
def menu_ranking(result: dict = Depends(dashboard)):
    return {"popular_menus": result["popular_menus"]}


@router.get("/stats/customers")
def customers(result: dict = Depends(dashboard)):
    return {key: result[key] for key in ("new_customers", "returning_customers", "age_groups", "genders")}


@router.get("/stats/ai-recommendations")
def ai_recommendations(result: dict = Depends(dashboard)):
    return result["ai"]


def insights(request: Request, settings: Settings = Depends(get_settings),
             repeat: int | None = Query(default=None, ge=2),
             regular: int | None = Query(default=None, ge=3),
             dormant: int | None = Query(default=None, ge=1)) -> dict:
    """집계용 주문을 한 번 읽어 추가 통계의 기준일과 등급 기준을 맞춘다."""
    rule = grade_rule(settings, repeat, regular, dormant, db=request.app.state.db)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    return stats_service.sales_insights(
        StatsStore(request.app.state.db).sales_orders(), request.app.state.members.all(),
        request.app.state.store_info.get()["tables"], datetime.now(KST).date(), rule)


@router.get("/stats/insights")
def all_insights(result: dict = Depends(insights)):
    """대시보드는 한 응답으로 읽어 그래프마다 조회 시점이 달라지는 것을 줄인다."""
    return result


def _part(result: dict, *keys: str) -> dict:
    """빈 주문은 모든 세부 API에서 같은 empty 응답으로 처리한다."""
    return {"empty": result["empty"], **({key: result[key] for key in keys} if not result["empty"] else {})}


@router.get("/stats/sales/hourly")
def hourly(result: dict = Depends(insights)):
    return _part(result, "by_hour", "peak_hour")


@router.get("/stats/sales/weekday")
def weekday(result: dict = Depends(insights)):
    return _part(result, "by_weekday", "peak_weekday")


@router.get("/stats/sales/trends")
def trends(result: dict = Depends(insights)):
    return _part(result, "days", "revenue", "daily_revenue", "today_revenue", "by_day", "last_day", "last_order_date",
                 "week_revenue", "week_change", "last_day_revenue", "last_day_change")


@router.get("/stats/sales/tickets")
def tickets(result: dict = Depends(insights)):
    return _part(result, "orders", "avg_ticket", "ticket_bands", "ai_avg_ticket", "plain_avg_ticket", "ai_share",
                 "member_avg_ticket", "guest_avg_ticket")


@router.get("/stats/tables")
def tables(result: dict = Depends(insights)):
    return _part(result, "tables", "turnover_today", "turnover_avg", "top_tables", "last_order_date")
