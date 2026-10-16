"""관리자 대시보드 통계 더미. (담당: 수용)"""


# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "GET /admin/api/stats": "dashboard_stats",
}


def dashboard_stats() -> dict:
    """대시보드 통계(고정 값). 실제 구현에서는 services/stats.py 의 dashboard() 가 주문·회원으로 계산한다."""
    return {
        "today_orders": 3, "avg_order_amount": 30666, "new_customers": 1, "returning_customers": 2,
        "age_groups": {"20대 미만": 1, "20대": 2, "30대": 1, "40대": 1, "50대 이상": 1},
        "genders": {"여": 3, "남": 3},
        "popular_menus": [{"name": "역전 옛날통닭 (한 마리·후라이드)", "qty": 17}, {"name": "생맥주 500cc", "qty": 8},
                          {"name": "감자튀김", "qty": 1}],
        "ai": {"recommendations": 9, "ai_orders": 3, "hit_rate": 0.333,
               "definition": "AI 조합이 포함된 주문 수 / 추천이 노출된 횟수 (임시 기준)"},
    }
