"""여러 관리자 데이터를 AI 마케팅 추천용 컨텍스트로 조립한다."""

import admin_repository as repo_mod
from admin.marketing.consumer_data import summarize_consumers
from admin.marketing.menu_data import summarize_menus
from admin.marketing.revenue_data import summarize_revenue
from admin_dummy_data import Unsupported


def build_marketing_context(repo, rule: dict) -> dict:
    """저장소 데이터 출처가 API든 더미든 같은 추천 입력 모양을 만든다."""
    stats = repo.stats(rule)
    menus, members, orders = repo.menus(), repo.members(rule), repo.orders()
    try:
        sms_logs, sms_usage = repo.sms_logs(), repo.sms_usage()
    except (Unsupported, repo_mod.api.ApiError, repo_mod.api.ApiUnavailable):
        # 문자 서버를 아직 구현하지 않은 환경에서도 AI 추천 화면은 독립적으로 보여야 한다.
        sms_logs, sms_usage = [], None

    revenue, ordered_items = summarize_revenue(orders)
    return {
        "stats": stats,
        "menus": summarize_menus(menus, ordered_items),
        "members": summarize_consumers(members),
        "orders": revenue,
        "sms": {"logs": len(sms_logs), "usage": sms_usage},
    }

