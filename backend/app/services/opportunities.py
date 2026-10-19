"""DB에서 읽은 매장 데이터로 관리자 AI 마케팅 추천 카드를 만든다."""

import hashlib
import json
import sys
from pathlib import Path

import httpx

# 서버를 backend/에서 실행해도 저장소 공통 모듈(shared/)을 읽을 수 있게 루트만 추가한다.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.services.grades import age_group, gender_label, grade_of
from app.services.sms_candidates import PROMPT as SMS_PROMPT  # AI 문자 페이지가 쓰는 문자 작성 지침을 그대로 재사용한다
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


# ---- 제미나이로 추천 문구 다듬기 ----
# 토큰을 아끼기 위해 ① 규칙 엔진이 이미 고른 카드(한 화면에 최대 8장)만 ② 한 번의 호출로 묶어서 보내고
# ③ 같은 입력은 결과를 기억해 두었다가 다시 부르지 않는다. 키가 없거나 실패하면 규칙 문구를 그대로 쓴다.
_REFINE_CACHE: dict[str, dict] = {}  # 입력 해시 -> {카드 번호: 다듬은 문구}
_REFINE_CACHE_MAX = 100
_GUIDE_PROMPT = (
    "당신은 호프집 사장님의 마케팅 비서입니다. 아래 카드마다 사장님이 오늘 바로 할 일을 한두 문장(60자 이내, 존댓말)으로 "
    "구체적으로 다시 써 주세요. 카드에 없는 숫자·할인·사실은 지어내지 마세요.")
_BATCH_RULE = (
    "\n\n입력은 JSON 배열이며 각 항목은 {i, kind, title, why, draft} 입니다. kind 가 sms 이면 위 지침대로 "
    "draft 를 고쳐 쓴 문자 본문을, guide 이면 사장님이 할 일을 쓰세요. 출력은 설명 없이 "
    '[{"i":번호,"text":"문구"}] 형태의 JSON 배열만 쓰세요.')


def _ask_gemini_batch(settings, cards: list[dict]) -> dict[int, str]:
    """카드 여러 장의 문구를 제미나이에 한 번에 요청한다. 실패하면 예외."""
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        timeout=20, headers={"x-goog-api-key": settings.gemini_api_key},
        json={"systemInstruction": {"parts": [{"text": SMS_PROMPT + " " + _GUIDE_PROMPT + _BATCH_RULE}]},
              "contents": [{"parts": [{"text": json.dumps(cards, ensure_ascii=False)}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}})
    r.raise_for_status()
    rows = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    return {int(row["i"]): str(row["text"]).strip() for row in rows if str(row.get("text", "")).strip()}


def refine_with_gemini(result: dict, settings) -> dict:
    """추천 카드의 문자 본문(sms)·할 일(guide)을 제미나이로 다듬는다. 각 카드에 source('ai'|'rule')를 붙인다."""
    # items 와 groups 는 같은 카드 객체를 공유한다. 두 목록의 카드를 모두 모으되 같은 카드는 한 번만 센다.
    cards = list({id(c): c for c in [*result["items"], *(c for k in ("sms", "guide") for c in result["groups"][k]["items"])]}.values())
    for card in cards:
        card["source"] = "rule"
    cards = [c for c in cards if c.get("why") and c["title"] != EMPTY_RECOMMENDATION["title"]]
    if not settings.gemini_api_key or not cards:
        return result
    payload = [{"i": n, "kind": c["action_type"], "title": c["title"], "why": c["why"],
                "draft": c["sms_body"] if c["action_type"] == "sms" and c["sms_body"] else c["action"]}
               for n, c in enumerate(cards)]
    key = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
    try:
        if key not in _REFINE_CACHE:
            if len(_REFINE_CACHE) >= _REFINE_CACHE_MAX:
                _REFINE_CACHE.pop(next(iter(_REFINE_CACHE)))  # 가장 오래된 것부터 비운다
            _REFINE_CACHE[key] = _ask_gemini_batch(settings, payload)
        texts = _REFINE_CACHE[key]
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        _REFINE_CACHE.pop(key, None)
        return result  # 실패하면 규칙 문구 그대로
    for n, card in enumerate(cards):
        text = texts.get(n)
        if not text:
            continue
        if card["action_type"] == "sms" and card["sms_body"]:
            card["sms_body"] = text
        else:
            card["action"] = text
        card["source"] = "ai"
    return result
