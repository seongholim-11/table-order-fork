"""관리자 대시보드 통계. [뼈대] 계산 로직은 비워 두었다 (지금은 routers/admin/stats.py 가 dummy.dashboard_stats() 를 돌려준다)."""

from datetime import date


def dashboard(orders: list[dict], members: list[dict], recommendations: int, today: date, rule: dict) -> dict:
    """오늘 통계를 계산한다. 돌려줄 키는 dummy.dashboard_stats() 와 같다.

    TODO: today_orders / avg_order_amount: 오늘(KST) 주문 수와 평균 주문 금액.
    TODO: new_customers / returning_customers: 오늘 주문한 회원을 grades.grade_of 로 나눠 신규 / (재방문+단골) 집계.
    TODO: age_groups(grades.AGE_GROUPS 순서) / genders: 전체 회원 분포.
    TODO: popular_menus: 메뉴별 수량 TOP10 (AI 조합은 구성 메뉴 단위로 계산).
    TODO: ai: recommendations, ai_orders(AI 조합 주문 수), hit_rate = ai_orders / recommendations (0 이면 None), definition.
    """
    raise NotImplementedError
