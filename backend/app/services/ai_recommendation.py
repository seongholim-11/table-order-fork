"""손님용 제미나이 추천 서비스.

제미나이는 DB에서 읽은 후보 중 어떤 조합이 어울리는지 고르고,
가격·수량·품절·예산 검증과 화면용 응답 조립은 서버가 담당한다.
이렇게 해야 모델이 임의의 메뉴나 가격을 만들어도 주문 데이터에 섞이지 않는다.
"""

import json
import re

import httpx

from app.core.settings import Settings


class AiRecommendationUnavailable(Exception):
    """제미나이 추천을 만들 수 없어 화면의 규칙 추천으로 대체해야 하는 경우."""


class AiRecommendationService:
    def __init__(self, settings: Settings, shop, ai_content):
        self.s = settings
        self.shop = shop
        self.ai_content = ai_content

    @staticmethod
    def _ordered_counts(lines: list[dict]) -> dict[str, int]:
        """장바구니·테이블 주문에서 메뉴별 수량을 뽑아 모델에 보낼 요약을 만든다."""
        counts: dict[str, int] = {}
        for line in lines:
            components = line.get("components") or []
            rows = components or [line]
            for row in rows:
                item_id = row.get("id")
                if not item_id or item_id.startswith(("combo:", "item:", "component:")):
                    continue
                qty = int(row.get("qty", 1)) * int(line.get("qty", 1) if components else 1)
                counts[item_id] = counts.get(item_id, 0) + qty
        return counts

    def _prompt(self, params: dict, menus: list[dict], rules: dict, order_counts: dict[str, int]) -> str:
        """DB 자료와 손님 답변을 모델이 오해하지 않도록 한글 프롬프트로 묶는다."""
        menu_rows = [
            {
                "id": m["id"], "name": m["name"], "category": m.get("cat"),
                "price": m["price"], "soldout": bool(m.get("soldout")),
                "spicy": m.get("spicy", 0), "set_ok": bool(m.get("set_ok", True)),
                "tags": m.get("tags", []), "weight": m.get("weight", 50),
            }
            for m in menus
        ]
        pairings = [
            {"id": p[0], "name": p[1], "menu_ids": p[2], "reason": p[3],
             "meta": rules.get("pair_meta", {}).get(p[0], {})}
            for p in rules.get("pairings", [])
        ]
        facts = {
            "answers": params,
            "ordered_menu_counts": order_counts,
            "discount_percent_for_member": rules.get("discount_percent", 0),
            "drinks": rules.get("drinks", {}),
            "hot_themed": rules.get("hot_themed", []),
            "pairings": pairings,
            "menus": menu_rows,
        }
        return (
            "손님용 메뉴 추천을 해 주세요. 아래 JSON은 서버 DB에서 읽은 최신 메뉴·재고·추천 규칙입니다.\n"
            "반드시 pairings의 id 중에서 1~3개만 골라 recommendations로 답하세요.\n"
            "이미 품절(soldout=true)이거나 set_ok=false인 메뉴가 들어간 조합은 고르지 마세요.\n"
            "손님의 인원·예산·맵기·음료와 주문 내역을 우선 반영하고, 추천 이유는 제공된 사실만 사용해 자연스러운 한국어로 1~2문장 작성하세요.\n"
            "가격·수량·할인율은 직접 계산하지 말고 서버가 계산하므로 응답에 넣지 마세요.\n"
            '응답 형식은 반드시 {"recommendations":[{"combo_id":"pairing id", "reason":"추천 이유"}]} 입니다.\n\n'
            f"DB와 손님 정보:\n{json.dumps(facts, ensure_ascii=False)}"
        )

    def _ask_gemini(self, prompt: str) -> dict:
        """제미나이에서 JSON 응답을 받고 파싱한다."""
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent",
            timeout=15,
            headers={"x-goog-api-key": self.s.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": "당신은 매장 메뉴 추천 전문가입니다. 지시한 JSON 형식만 출력하세요."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "recommendations": {
                                "type": "ARRAY",
                                "minItems": 1,
                                "maxItems": 3,
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "combo_id": {"type": "STRING"},
                                        "reason": {"type": "STRING"},
                                    },
                                    "required": ["combo_id", "reason"],
                                },
                            }
                        },
                        "required": ["recommendations"],
                    },
                },
            },
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("제미나이 응답이 객체가 아닙니다.")
        return data

    @staticmethod
    def _safe_reason(value: object, fallback: str) -> str:
        """모델이 반환한 설명을 짧은 일반 텍스트로 제한한다."""
        reason = str(value or fallback).replace("\r", " ").replace("\n", " ").strip()
        return reason[:300] or fallback

    def _build_combo(self, pairing: dict, params: dict, menus_by_id: dict, rules: dict,
                     member: bool, reason: str) -> dict | None:
        people = max(int(params.get("people", 2)), 1)
        budget = max(int(params.get("budget", 40000)), 1)
        spicy = params.get("spicy", "상관없어요")
        drink = params.get("drink", "맥주")
        hunger = params.get("hunger", "적당해요")
        ids = tuple(pairing["menu_ids"])
        if spicy == "매콤하게":
            ids = tuple(f"{item_id}-hot" if item_id in ("a2", "a3") else item_id for item_id in ids)
        drink_id = rules.get("drinks", {}).get(drink)
        selected_ids = list(ids) + ([drink_id] if drink_id else [])
        if any(item_id not in menus_by_id for item_id in selected_ids):
            return None
        if any(menus_by_id[item_id].get("soldout") for item_id in selected_ids):
            return None
        if any(not menus_by_id[item_id].get("set_ok", True) for item_id in ids):
            return None
        spicy_items = [menus_by_id[item_id] for item_id in ids
                       if int(menus_by_id[item_id].get("spicy", 0)) >= 2
                       or "매운맛" in menus_by_id[item_id].get("tags", [])]
        if spicy == "맵지 않게" and (pairing["id"] in set(rules.get("hot_themed", [])) or spicy_items):
            return None

        portions = 2 if people >= 4 else 1
        if hunger == "매우 배고파요":
            portions += 1
        elif hunger == "출출해요" and people >= 3:
            portions = max(portions, 2)
        components = []
        for item_id in selected_ids:
            item = menus_by_id[item_id]
            qty = people if item_id == drink_id else portions
            components.append({"id": item_id, "name": item["name"], "emoji": item.get("emoji", ""),
                               "qty": qty, "opt": "", "unit": item["price"]})
        original = sum(component["unit"] * component["qty"] for component in components)
        discount_percent = rules.get("discount_percent", 0) if member else 0
        discount = original * discount_percent // 100
        price = original - discount
        if price > budget:
            return None
        return {
            "id": pairing["id"], "name": pairing["name"], "components": components,
            "original": original, "discount": discount, "price": price,
            "reason": self._safe_reason(reason, pairing["reason"]), "score": 0,
        }

    def generate(self, params: dict, lines: list[dict], member: bool) -> dict:
        """DB 자료를 제미나이에 제공하고 검증된 조합을 화면 모양으로 반환한다."""
        if not self.s.gemini_api_key:
            raise AiRecommendationUnavailable("GEMINI_API_KEY가 설정되지 않았습니다.")
        menus = self.shop.menus()
        rules = self.ai_content.rules()
        # 질문 결과에 날씨가 없을 때도 DB에 저장된 현재 날씨를 추천 근거로 넣는다.
        params = dict(params)
        params.setdefault("weather", self.ai_content.weather_shape().get("current"))
        counts = self._ordered_counts(lines)
        prompt = self._prompt(params, menus, rules, counts)
        try:
            data = self._ask_gemini(prompt)
            raw = data.get("recommendations", [])
            if not isinstance(raw, list):
                raise ValueError("recommendations가 배열이 아닙니다.")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AiRecommendationUnavailable("제미나이 추천을 만들지 못했습니다.") from exc

        pairings = {p[0]: {"id": p[0], "name": p[1], "menu_ids": p[2], "reason": p[3]}
                    for p in rules.get("pairings", [])}
        menus_by_id = {m["id"]: m for m in menus}
        combos = []
        used = set()
        for row in raw:
            if not isinstance(row, dict):
                continue
            combo_id = str(row.get("combo_id", "")).strip()
            if combo_id in used or combo_id not in pairings:
                continue
            combo = self._build_combo(pairings[combo_id], params, menus_by_id, rules, member, row.get("reason"))
            if combo is not None:
                used.add(combo_id)
                combos.append(combo)
            if len(combos) == 3:
                break
        if not combos:
            raise AiRecommendationUnavailable("유효한 추천 조합이 없습니다.")
        return {"source": "gemini", "combos": combos}
