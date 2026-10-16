"""주문 데이터를 매출·인기 메뉴·혼잡 시간 정보로 정리한다."""

from collections import Counter


def _ordered_items(orders) -> Counter:
    """'메뉴명 x수량' 문자열을 메뉴별 주문 수량으로 합산한다."""
    quantities: Counter = Counter()
    for text in orders["주문 내역"] if len(orders) else []:
        for part in text.split(", "):
            name, _, quantity = part.rpartition(" x")
            if name:
                quantities[name] += int(quantity or 1)
    return quantities


def summarize_revenue(orders) -> tuple[dict, Counter]:
    """주문 표에서 추천 카드와 상단 지표에 쓸 매출 요약을 만든다."""
    quantities = _ordered_items(orders)
    hours = Counter(value.hour for value in orders["주문 시각"]) if len(orders) else Counter()
    weekdays = Counter(value.weekday() for value in orders["주문 시각"]) if len(orders) else Counter()
    summary = {
        "count": len(orders),
        "revenue": int(orders["금액"].sum()) if len(orders) else 0,
        "avg": int(orders["금액"].mean()) if len(orders) else 0,
        "peak_hours": [hour for hour, _ in hours.most_common(3)],
        "busy_weekday": weekdays.most_common(1)[0][0] if weekdays else None,
        "top_items": quantities.most_common(5),
    }
    return summary, quantities

