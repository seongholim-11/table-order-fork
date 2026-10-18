"""관리자 API: 고객 목록과 중복되지 않는 메뉴 품절 알림."""

from fastapi import APIRouter, Request

from app.services.stats import menu_stock_alerts
from app.stores.stats import StatsStore

router = APIRouter()


@router.get("/alerts")
def alerts(request: Request):
    """조회할 때 현재 DB를 읽어 재입고·추가 주문을 다음 새로고침에 반영한다."""
    store = StatsStore(request.app.state.db)
    return menu_stock_alerts(store.menu_stock(), store.menu_sales())
