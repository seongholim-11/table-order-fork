"""DB에서 읽은 매장 데이터로 관리자 AI 마케팅 추천 카드를 만든다."""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

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


# ---- 제미나이로 추천 문구 다듬기 ----
# 토큰을 아끼기 위해 ① 규칙 엔진이 이미 고른 카드(한 화면에 최대 8장)만 ② 한 번의 호출로 묶어서 보내고
# ③ 같은 입력은 결과를 기억해 두었다가 다시 부르지 않는다. 키가 없거나 실패하면 규칙 문구를 그대로 쓴다.
_REFINE_CACHE: dict[str, dict] = {}  # 입력 해시 -> {카드 번호: 다듬은 문구}
_REFINE_CACHE_MAX = 100
_GUIDE_PROMPT = (
    "당신은 호프집 사장님의 마케팅 비서입니다. 아래 카드마다 사장님이 오늘 바로 할 일을 한두 문장(60자 이내, 존댓말)으로 "
    "구체적으로 다시 써 주세요. 카드에 없는 숫자·할인·사실은 지어내지 마세요.")
_BATCH_RULE = (
    "\n\n입력은 JSON 배열이며 각 항목은 {i, title, why, draft} 입니다. draft 를 고쳐 쓴 할 일을 쓰세요. 출력은 설명 없이 "
    '[{"i":번호,"text":"문구"}] 형태의 JSON 배열만 쓰세요.')


def _ask_gemini_batch(settings, cards: list[dict]) -> dict[int, str]:
    """카드 여러 장의 문구를 제미나이에 한 번에 요청한다. 실패하면 예외."""
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        timeout=20, headers={"x-goog-api-key": settings.gemini_api_key},
        json={"systemInstruction": {"parts": [{"text": _GUIDE_PROMPT + _BATCH_RULE}]},
              "contents": [{"parts": [{"text": json.dumps(cards, ensure_ascii=False)}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}})
    r.raise_for_status()
    rows = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    return {int(row["i"]): str(row["text"]).strip() for row in rows if str(row.get("text", "")).strip()}


_SMS_CACHE: dict[tuple, str] = {}  # (카드 제목, 키워드, 사실 요약) -> 만든 문자 본문
SMS_WORKERS = 4  # 문자 카드 문구를 동시에 만드는 최대 개수 (한 화면의 문자 추천은 최대 네 장)


def _keywords_for(grades: list[str], info: dict) -> list[str]:
    """추천 카드의 수신 등급으로 AI 문자 페이지(sms_candidates)가 쓰는 키워드 조합을 고른다."""
    if "휴면" in grades:
        keywords = ["휴면"]
    elif "단골" in grades:
        keywords = ["주문", "단골"]
    else:
        keywords = ["가중치", "주문"]
    # 오늘 날씨·주변 행사 정보가 있으면 문구에 한 줄씩 더한다(없는 정보를 지어내지 않도록 값이 있을 때만)
    if info.get("weather_text", "").strip():
        keywords.append("날씨")
    if info.get("event_text", "").strip():
        keywords.append("행사")
    return keywords


def _refine_sms_cards(cards: list[dict], sms_service, refresh: bool) -> None:
    """문자 카드의 본문을 기존 AI 문자 페이지의 생성 로직(SmsCandidateService.generate)으로 만든다.

    날씨·행사는 sms_service.external.today() 가 하루 한 번만 외부에서 가져와 저장해 둔 값을 쓴다.
    제미나이를 못 쓰면(키 없음·실패) 규칙 엔진의 문구를 그대로 둔다.
    """
    targets = [c for c in cards if c.get("action_type") == "sms" and c.get("sms_body")]
    if not targets or not sms_service.s.gemini_api_key:
        return
    try:
        summary, info = sms_service.summary(), sms_service.external.today()
        facts = sms_service._facts(summary, info)
    except Exception:  # 매장 데이터·외부 정보를 못 읽어도 추천 화면은 규칙 문구로 계속 보여 준다
        return
    fact_key = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def make(card):
        keywords = _keywords_for(card.get("target_grades") or [], info)
        key = (card["title"], tuple(keywords), fact_key)
        if refresh:
            _SMS_CACHE.pop(key, None)
        if key not in _SMS_CACHE:
            text, source = sms_service.generate(keywords, facts)
            if source != "ai":
                return  # 템플릿으로 떨어졌으면 규칙 문구를 유지한다
            if len(_SMS_CACHE) >= _REFINE_CACHE_MAX:
                _SMS_CACHE.pop(next(iter(_SMS_CACHE)))
            _SMS_CACHE[key] = text
        card["sms_body"], card["source"] = _SMS_CACHE[key], "ai"

    with ThreadPoolExecutor(max_workers=SMS_WORKERS) as pool:  # 카드별 호출을 동시에 보내 기다리는 시간을 줄인다
        list(pool.map(make, targets))


def refine_with_gemini(result: dict, settings, refresh: bool = False, sms_service=None) -> dict:
    """추천 카드를 제미나이로 다듬는다. 각 카드에 source('ai'|'rule')를 붙인다.

    - 문자 카드의 본문: 기존 AI 문자 생성 로직(sms_service)으로 만든다.
    - 기타(guide) 카드의 할 일: 한 번의 묶음 호출로 다듬는다.
    refresh=True(재추천)면 저장해 둔 결과를 버리고 새로 만든다."""
    # items 와 groups 는 같은 카드 객체를 공유한다. 두 목록의 카드를 모두 모으되 같은 카드는 한 번만 센다.
    cards = list({id(c): c for c in [*result["items"], *(c for k in ("sms", "guide") for c in result["groups"][k]["items"])]}.values())
    for card in cards:
        card["source"] = "rule"
    cards = [c for c in cards if c.get("why") and c["title"] != EMPTY_RECOMMENDATION["title"]]
    if not settings.gemini_api_key or not cards:
        return result
    if sms_service is not None:
        _refine_sms_cards(cards, sms_service, refresh)
    # 문자 본문이 있는 카드는 위에서 처리했으므로, 나머지 카드의 할 일만 묶음 호출로 다듬는다.
    cards = [c for c in cards if not (c.get("action_type") == "sms" and c.get("sms_body"))]
    if not cards:
        return result
    payload = [{"i": n, "title": c["title"], "why": c["why"], "draft": c["action"]} for n, c in enumerate(cards)]
    key = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
    if refresh:
        _REFINE_CACHE.pop(key, None)
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
        if texts.get(n):
            card["action"], card["source"] = texts[n], "ai"
    return result
