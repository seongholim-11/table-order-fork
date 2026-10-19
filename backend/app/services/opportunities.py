"""DB에서 읽은 매장 데이터로 관리자 AI 마케팅 추천 카드를 만든다."""

import sys
from pathlib import Path

# 서버를 backend/에서 실행해도 저장소 공통 모듈(shared/)을 읽을 수 있게 루트만 추가한다.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.services.grades import age_group, gender_label, grade_of
from shared.opportunity_engine import (EMPTY_RECOMMENDATION, PAGE_SIZE,
                                       build_context as build_shared_context,
                                       pick_recommendations, recommend)


def build_context(orders: list[dict], members: list[dict], menus: list[dict], stats: dict,
                  today, rule: dict) -> dict:
    """DB 행을 공통 추천 엔진의 입력 모양으로 바꾼다."""
    normalized_members = [{
        "id": member["id"], "nickname": member["nickname"],
        "gender": gender_label(member.get("gender")),
        "age_group": age_group(member.get("birth_year"), today),
        "birthday": member.get("birthday"), "visit_count": member.get("visit_count", 0),
        "last_visit_at": member.get("last_visit_at"), "has_phone": bool(member.get("phone")),
        "marketing_consent": bool(member.get("marketing_consent")),
        "opted_out": bool(member.get("opted_out")), "grade": grade_of(member, today, **rule),
    } for member in members]
    normalized_menus = [{
        "name": menu["name"], "category": menu.get("cat", "기타"),
        "spicy": int(menu.get("spicy") or 0), "soldout": bool(menu.get("soldout")),
        "weight": int(menu.get("weight") or 0),
    } for menu in menus]
    return build_shared_context(normalized_members, orders, normalized_menus, stats, today, rule=rule)


def opportunities(orders: list[dict], members: list[dict], menus: list[dict], stats: dict,
                  today, rule: dict, round_no: int) -> dict:
    """DB 자료를 매 요청마다 다시 집계해 해당 회차의 서로 다른 추천 네 개를 반환한다."""
    context = build_context(orders, members, menus, stats, today, rule)
    result = pick_recommendations(recommend(context), round_no)
    # 화면 계약은 유지하되 추천 화면에서는 카드에만 집중하도록 이 요약을 표시하지 않는다.
    result["summary"] = {
        "members": {key: value for key, value in context["members"].items()
                    if key in ("total", "grades", "sendable", "opted_out", "pool_by_grade")},
        "orders": {key: value for key, value in context["orders"].items()
                   if key in ("count", "revenue", "avg", "peak_hours", "top_items")},
    }
    return result
