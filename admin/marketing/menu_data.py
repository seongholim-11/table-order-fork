"""메뉴 데이터를 판매·품절·추천 가중치 관점으로 정리한다."""


def summarize_menus(menus, ordered_items) -> dict:
    """메뉴 표와 주문 수량을 비교해 팔리지 않은 메뉴까지 찾는다."""
    if menus.empty:
        return {"total": 0, "on_sale": 0, "soldout": [], "high_weight": [], "unsold": []}

    on_sale = menus[menus["판매 여부"]]
    return {
        "total": len(menus),
        "on_sale": len(on_sale),
        "soldout": menus[~menus["판매 여부"]]["메뉴명"].tolist(),
        "high_weight": menus.nlargest(3, "추천 가중치")["메뉴명"].tolist(),
        "unsold": [name for name in on_sale["메뉴명"].tolist() if ordered_items[name] == 0],
    }

