"""관리자 화면이 쓰는 모든 데이터의 단일 출입구.

구조: 화면(app.py) → AdminRepository(JSON → 화면용 표 변환, 한 곳) → Backend(더미 또는 서버)
 - DummyBackend(dummy_data.py): 서버와 똑같은 JSON 을 돌려주는 가짜 서버
 - ApiBackend: 실제 서버 호출 (아래 ENDPOINTS 가 경로 목록)
둘은 같은 메서드·같은 JSON 을 돌려주므로 화면 코드는 바꿀 필요가 없다.

데이터 소스 전환: 환경 변수 DATA_SOURCE
  dummy : 더미만 (서버 불필요, 로그인은 ADMIN_TOKEN 과 비교)
  api   : 서버만. 서버가 안 닿으면 로그인 실패
  auto  : 서버가 닿으면 API, 안 닿으면 더미 (기본값)

새 데이터를 API로 바꾸려면: ENDPOINTS 에 경로를 적고 → ApiBackend 와 DummyBackend 에 같은 이름의
메서드를 추가하고 → AdminRepository 에 표 변환을 추가한다.
"""
import os
import re
import sys
import uuid
from html import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from admin_dummy_data import GRADES, DummyBackend  # noqa: E402, F401  (GRADES 는 화면에서 여기서 가져간다)
from shared import api  # noqa: E402

ENDPOINTS = {
    "store": "/api/v1/store",
    "menus": "/admin/api/menus",              # GET {categories, menus} / PUT 한 건·목록 / DELETE /{id}
    "roulette": "/api/v1/roulette/prizes",  # GET 칸 목록 / PUT 관리자 경로로 전체 교체
    "categories": "/admin/api/categories",    # 관리자 목록(가상 포함·메뉴 개수 포함)
    "members": "/admin/api/members",          # GET ?repeat&regular&dormant
    "orders": "/admin/api/orders",
    "stats": "/admin/api/stats",
    "calls": "/admin/api/calls",
    "sms": "/admin/api/marketing/sms",        # /usage /preview /send /logs
    "opportunities": "/admin/api/marketing/opportunities",  # DB 기반 마케팅 추천 카드
    "growth_performance": "/admin/api/marketing/growth-performance",  # DB 기반 AI 도입 전후 매출 성과
    "chat": "/admin/api/marketing/chat/sessions",  # AI 챗봇 대화방 (/{id}, /{id}/messages)
    "opt_out": "/admin/api/members/{id}/opt-out",
}
KST = timezone(timedelta(hours=9))
SPICY_LABELS = {0: "안 매움", 1: "순한맛", 2: "보통맛", 3: "아주 매움"}
SPICY_VALUES = {v: k for k, v in SPICY_LABELS.items()}
MODES = ("dummy", "api", "auto")
DEFAULT_RULE = {"repeat": 2, "regular": 5, "dormant": 30}
MENU_COLUMNS = ["id", "메뉴명", "카테고리", "가격", "설명", "이미지 URL", "판매 여부", "매운 정도", "추천 가중치", "세트 가능"]


class ApiBackend:
    """서버 호출. 반환값은 서버가 준 JSON 그대로 (DummyBackend 와 같은 모양)."""
    source = "api"

    def __init__(self, token: str):
        self.token = token

    def login(self, token: str) -> bool:
        """토큰이 맞으면 True, 틀리면 False. 서버가 안 닿으면 ApiUnavailable."""
        try:
            api.get(ENDPOINTS["menus"], token)
            self.token = token
            return True
        except api.ApiError as e:
            if e.status == 401:
                return False
            raise

    def store(self):
        return api.get(ENDPOINTS["store"])

    def menus(self):
        return api.get(ENDPOINTS["menus"], self.token)

    def categories_full(self):
        return api.get(ENDPOINTS["categories"], self.token)

    def category_list(self):
        """실제 메뉴 카테고리와 메뉴 개수를 API에서 그대로 가져온다."""
        return [category for category in self.categories_full() if category["id"] not in VIRTUAL_CATEGORIES]

    def save_categories(self, categories):
        # 구형 전체 교체 호출은 새 개별 API로 옮긴 뒤에도 호환용으로 남겨 둔다.
        return api.put("/admin/api/content/categories", self.token, json=categories)

    def add_category(self, category):
        return api.post(ENDPOINTS["categories"], self.token, json=category)

    def update_category(self, category_id, fields):
        return api.patch(f"{ENDPOINTS['categories']}/{category_id}", self.token, json=fields)

    def delete_category(self, category_id):
        return api.delete(f"{ENDPOINTS['categories']}/{category_id}", self.token)

    def roulette_prizes(self):
        return api.get(ENDPOINTS["roulette"])

    def save_roulette_prizes(self, prizes):
        return api.put("/admin/api/owner/roulette/prizes", self.token, json=prizes)

    def save_menu(self, menu_id, fields):
        return api.put(f"{ENDPOINTS['menus']}/{menu_id}", self.token, json=fields)

    def save_menus(self, items):
        # 목록 첫 메뉴 ID를 기존 PUT 경로에 넣고, 여러 메뉴 변경을 한 요청으로 보낸다.
        return api.put(f"{ENDPOINTS['menus']}/{items[0]['id']}", self.token, json=items)

    def delete_menu(self, menu_id):
        return api.delete(f"{ENDPOINTS['menus']}/{menu_id}", self.token)

    def members(self, rule):
        return api.get(ENDPOINTS["members"], self.token, params=rule)

    def customer_grades(self, rule):
        """고객 등급 카드와 대시보드가 함께 쓰는 서버 집계 결과."""
        return api.get("/admin/api/customers/grades", self.token, params=rule)

    def customer_grade_rules(self):
        """서버에 설정된 기본 등급 기준을 조회한다."""
        return api.get("/admin/api/customers/grades/rules", self.token)

    def save_customer_grade_rules(self, rule):
        """화면 미리보기와 구분해서 관리자가 저장을 누를 때만 요청한다."""
        return api.put("/admin/api/customers/grades/rules", self.token, json=rule)

    def orders(self):
        return api.get(ENDPOINTS["orders"], self.token)

    def stats(self, rule):
        # 미리 본 등급 기준을 오늘 신규·재방문 집계에도 적용한다.
        return api.get(ENDPOINTS["stats"], self.token, params=rule)

    def sales_insights(self, rule):
        """추가 통계 전체를 한 번에 읽어 그래프마다 주문을 다시 조회하지 않는다."""
        return api.get(f"{ENDPOINTS['stats']}/insights", self.token, params=rule)

    def menu_alerts(self):
        """품절 상태와 인기 메뉴 여부를 실제 DB에서 조회한다."""
        return api.get("/admin/api/alerts", self.token)

    def calls(self):
        return api.get(ENDPOINTS["calls"], self.token)

    def call_done(self, call_id):
        return api.post(f"{ENDPOINTS['calls']}/{call_id}/done", self.token)

    def sms_usage(self):
        return api.get(f"{ENDPOINTS['sms']}/usage", self.token)

    def sms_balance(self):
        return api.get(f"{ENDPOINTS['sms']}/balance", self.token)

    def sms_preview(self, grades, body, scheduled_at=None, member_ids=None):
        return api.post(f"{ENDPOINTS['sms']}/preview", self.token, json=_sms_body(grades, body, scheduled_at, member_ids))

    def sms_send(self, grades, body, scheduled_at=None, member_ids=None):
        return api.post(f"{ENDPOINTS['sms']}/send", self.token, json=_sms_body(grades, body, scheduled_at, member_ids))

    def sms_cancel(self, log_id):
        return api.post(f"{ENDPOINTS['sms']}/logs/{log_id}/cancel", self.token)

    def sms_candidates(self):
        """AI 문자 후보 [{keywords, grades, body, source}] 를 서버가 만들어 준다 (날씨·행사·매장 데이터 반영)."""
        # 서버가 날씨·행사·AI 를 차례로 부르면 기본 제한(5초)을 넘기 쉬워 이 호출만 넉넉히 기다린다
        return api.post(f"{ENDPOINTS['sms']}/candidates", self.token, timeout=60)

    def sms_logs(self):
        return api.get(f"{ENDPOINTS['sms']}/logs", self.token)

    def opportunities(self, round_no=0):
        """서버가 DB 자료로 계산한 네 장의 마케팅 추천을 읽는다."""
        return api.get(ENDPOINTS["opportunities"], self.token, params={"round": round_no})

    def growth_performance(self):
        # backend/app/services/growth_performance.py가 orders·members DB를 읽어 계산한다.
        return api.get(ENDPOINTS["growth_performance"], self.token)

    # ---- AI 챗봇: 대화방·메시지는 서버가 DB 에 저장한다 ----
    def chat_sessions(self):
        return api.get(ENDPOINTS["chat"], self.token)

    def chat_create(self):
        return api.post(ENDPOINTS["chat"], self.token)

    def chat_get(self, session_id):
        return api.get(f"{ENDPOINTS['chat']}/{session_id}", self.token)

    def chat_send(self, session_id, content):
        """질문을 보내 [질문, 답변] 메시지를 받는다. 서버가 DB 를 읽고 제미나이를 부르므로 넉넉히 기다린다."""
        return api.post(f"{ENDPOINTS['chat']}/{session_id}/messages", self.token, json={"content": content}, timeout=60)["messages"]

    def opt_out(self, member_id):
        return api.post(ENDPOINTS["opt_out"].format(id=member_id), self.token)


def _sms_body(grades, body, scheduled_at, member_ids=None) -> dict:
    data = {"grades": grades, "body": body}
    if member_ids is not None:
        data["member_ids"] = [int(i) for i in member_ids]
    if scheduled_at:
        data["scheduled_at"] = scheduled_at.isoformat()  # 시간대 없으면 서버가 KST 로 본다
    return data


VIRTUAL_CATEGORIES = {"ai", "best"}  # 손님 화면에만 있는 가상 카테고리(AI 추천 조합·인기메뉴). 메뉴를 직접 넣지 않는다
ICON_DEFAULT = "🍽️"
# 새 카테고리의 메뉴 카드 배경색(손님 화면 그라데이션). 이름 → [시작색, 끝색]
COLOR_PRESETS = {"주황": ["#f6b93b", "#e55039"], "초록": ["#b8e994", "#38ada9"], "빨강": ["#ff6b6b", "#7d1d3f"],
                 "노랑": ["#fbc531", "#c27c0e"], "파랑": ["#74b9ff", "#2d3a8c"], "보라": ["#a29bfe", "#4b3f9e"]}


ROULETTE_MIN_SLOTS, ROULETTE_MAX_SLOTS = 2, 8
ROULETTE_COLUMNS = ["서비스 메뉴", "종류", "할인율(%)", "확률 가중치", "색상"]
ROULETTE_KINDS = {"discount": "할인", "free": "서비스"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
SERVICE_MENU_IDS = ("a1", "a4", "a11", "d7", "d8", "d1", "j1", "b1")
SERVICE_MENU_NAMES = {"a1": "맛보기 먹태구이", "d1": "탄산음료", "j1": "소주 1병", "b1": "생맥주 1잔"}
ALL_MENU_LABEL = "[할인] 전체 메뉴"


def _service_menu_allowed(menu: dict) -> bool:
    """사장님이 정한 맛보기·간식·음료 메뉴만 룰렛 서비스로 허용한다."""
    return menu["id"] in SERVICE_MENU_IDS


def _menu_emoji(name: str, original: str = "") -> str:
    """메뉴 이름을 보고 서비스 카드에 어울리는 이모지를 자동 배정한다."""
    emoji_rules = (("계란", "🥚"), ("감자", "🍟"), ("치즈볼", "🧀"), ("닭똥집", "🍗"), ("오징어", "🦑"),
                   ("새우", "🍤"), ("먹태", "🐟"), ("떡볶이", "🌶️"), ("노가리", "🐟"), ("건어물", "🦑"), ("콜라", "🥤"),
                   ("탄산", "🥤"), ("사이다", "🥤"), ("소주", "🍶"), ("생맥주", "🍺"), ("라면", "🍜"),
                   ("주먹밥", "🍙"), ("공깃밥", "🍚"), ("땅콩", "🥜"))
    return next((emoji for word, emoji in emoji_rules if word in name), original if original and original != "🍽️" else "🍴")


class CategoryError(Exception):
    """카테고리 이름 중복·빈 이름·메뉴가 남은 카테고리 삭제 같은 입력 문제 (화면에 그대로 보여줄 수 있는 메시지)."""


class AdminRepository:
    """백엔드 JSON → 화면용 표/값. 더미든 서버든 같은 변환을 쓴다."""

    def __init__(self, backend):
        self.backend = backend

    @property
    def source(self) -> str:
        return self.backend.source

    def store(self) -> dict:
        """대시보드 계산에 필요한 매장명·테이블 수를 데이터 출처와 관계없이 돌려준다."""
        return self.backend.store()

    # ---- 메뉴 ----
    def categories(self) -> list[dict]:
        return self.backend.menus()["categories"]

    def menus(self) -> pd.DataFrame:
        payload = self.backend.menus()
        names = {c["id"]: c["name"] for c in payload["categories"]}
        rows = [{"id": m["id"], "메뉴명": m["name"], "카테고리": names.get(m["cat"], m["cat"]), "가격": m["price"],
                 "설명": m["desc"], "이미지 URL": m["image_url"], "판매 여부": not m["soldout"],
                 "매운 정도": SPICY_LABELS.get(m["spicy"], "안 매움"), "추천 가중치": m["weight"], "세트 가능": m["set_ok"]}
                for m in payload["menus"]]
        return pd.DataFrame(rows, columns=MENU_COLUMNS)

    # ---- 카테고리 CRUD (왼쪽 패널) ----
    def category_list(self) -> list[dict]:
        """메뉴를 넣을 수 있는 카테고리(가상 카테고리 제외): id, icon, name, colors, menu_count."""
        if hasattr(self.backend, "category_list"):
            return self.backend.category_list()
        counts: dict[str, int] = {}
        for m in self.backend.menus()["menus"]:
            counts[m["cat"]] = counts.get(m["cat"], 0) + 1
        return [{**c, "menu_count": counts.get(c["id"], 0)} for c in self.backend.categories_full()
                if c["id"] not in VIRTUAL_CATEGORIES]

    def _save_categories(self, mutate) -> None:
        """더미 백엔드의 기존 인터페이스를 위해 전체 목록 교체를 유지한다."""
        full = self.backend.categories_full()
        mutate(full)
        self.backend.save_categories(full)

    @staticmethod
    def _clean_name(name: str, others: list[dict]) -> str:
        name = (name or "").strip()
        if not name:
            raise CategoryError("카테고리 이름을 입력해 주세요.")
        if any(c["name"] == name for c in others):
            raise CategoryError(f"'{name}' 카테고리가 이미 있어요.")
        return name

    def add_category(self, name: str, icon: str = ICON_DEFAULT, color: str = "보라") -> str:
        """새 카테고리를 만들고 id 를 돌려준다."""
        new_id = f"cat{uuid.uuid4().hex[:6]}"

        clean_name = self._clean_name(name, self.backend.categories_full())
        category = {"id": new_id, "icon": (icon or "").strip() or ICON_DEFAULT,
                    "name": clean_name, "colors": COLOR_PRESETS.get(color, COLOR_PRESETS["보라"])}
        if hasattr(self.backend, "add_category"):
            self._call_category_api(self.backend.add_category, category)
        else:
            self._save_categories(lambda full: full.append(category))
        return new_id

    def update_category(self, category_id: str, name: str, icon: str, color: str | None = None) -> None:
        full = self.backend.categories_full()
        target = next((c for c in full if c["id"] == category_id), None)
        if target is None:
            raise CategoryError("없는 카테고리예요.")
        fields = {"name": self._clean_name(name, [c for c in full if c is not target]),
                  "icon": (icon or "").strip() or ICON_DEFAULT}
        if color:
            fields["colors"] = COLOR_PRESETS.get(color, target["colors"])
        if hasattr(self.backend, "update_category"):
            self._call_category_api(self.backend.update_category, category_id, fields)
            return

        def edit(full):
            target = next((c for c in full if c["id"] == category_id), None)
            if target is None:
                raise CategoryError("없는 카테고리예요.")
            target["name"] = self._clean_name(name, [c for c in full if c is not target])
            target["icon"] = (icon or "").strip() or ICON_DEFAULT
            if color:
                target["colors"] = COLOR_PRESETS.get(color, target["colors"])
        self._save_categories(edit)

    def delete_category(self, category_id: str) -> None:
        """메뉴가 남아 있으면 지울 수 없다(메뉴가 길을 잃지 않게)."""
        used = next((c["menu_count"] for c in self.category_list() if c["id"] == category_id), 0)
        if used:
            raise CategoryError(f"메뉴 {used}개가 남아 있어요. 메뉴를 먼저 옮기거나 삭제해 주세요.")

        if hasattr(self.backend, "delete_category"):
            self._call_category_api(self.backend.delete_category, category_id)
            return

        def remove(full):
            full[:] = [c for c in full if c["id"] != category_id]
        self._save_categories(remove)

    @staticmethod
    def _call_category_api(method, *args):
        """서버 검증 메시지를 화면의 기존 CategoryError로 이어 준다."""
        try:
            return method(*args)
        except api.ApiError as error:
            raise CategoryError(error.detail) from error

    # ---- 메뉴 등록 (선택한 카테고리에) ----
    def add_menu(self, category_id: str, name: str, price: int, desc: str = "", image_url: str = "",
                 soldout: bool = False, spicy: str = "안 매움", weight: int = 50, set_ok: bool = False) -> str:
        name = (name or "").strip()
        if not name:
            raise CategoryError("메뉴 이름을 입력해 주세요.")
        menu_id = f"m{uuid.uuid4().hex[:6]}"
        self.backend.save_menu(menu_id, {"name": name, "cat": category_id, "price": int(price), "desc": desc.strip(),
                                         "image_url": image_url.strip(), "soldout": soldout,
                                         "spicy": SPICY_VALUES.get(spicy, 0), "weight": int(weight), "set_ok": set_ok})
        return menu_id

    def save_menus(self, new: pd.DataFrame, old: pd.DataFrame) -> dict:
        """표에서 바뀐 행만 저장하고, 지워진 행은 삭제한다. {'saved': n, 'deleted': n}"""
        ids = {c["name"]: c["id"] for c in self.categories()}
        old_by_id = {r["id"]: r for r in old.to_dict("records")}
        changed, seen = [], set()
        for row in new.to_dict("records"):
            menu_id = row["id"] if isinstance(row["id"], str) and row["id"] else f"m{uuid.uuid4().hex[:6]}"
            seen.add(menu_id)
            if old_by_id.get(menu_id) == {**row, "id": menu_id}:
                continue  # 바뀌지 않은 행
            changed.append({
                "id": menu_id,
                "name": row["메뉴명"], "cat": ids[row["카테고리"]], "price": int(row["가격"]), "desc": _text(row["설명"]),
                "image_url": _text(row["이미지 URL"]), "soldout": not bool(row["판매 여부"]),
                "spicy": SPICY_VALUES.get(row["매운 정도"], 0), "weight": int(row["추천 가중치"]),
                "set_ok": bool(row["세트 가능"])})
        deleted = [i for i in old_by_id if i not in seen]
        # 체크 삭제와 나머지 행 수정도 같은 목록에 넣어 한 트랜잭션으로 보낸다.
        batch = changed + [{"id": menu_id, "delete": True} for menu_id in deleted]
        if batch:
            self.backend.save_menus(batch)
        return {"saved": len(changed), "deleted": len(deleted)}

    def save_menu_batch(self, items: list[dict]) -> dict:
        """같은 메뉴 PUT API로 여러 행의 일부 필드를 한 번에 저장한다."""
        return self.backend.save_menus(items)

    # ---- 이벤트: 룰렛 ----
    def roulette_menu_choices(self) -> list[dict]:
        """서비스 가능한 메뉴만 카테고리 순으로 묶어 선택 목록을 만든다."""
        payload = self.backend.menus()
        category_names = {category["id"]: category["name"] for category in payload["categories"]}
        category_order = {category["id"]: order for order, category in enumerate(payload["categories"])}
        choices = []
        menus = sorted(payload["menus"], key=lambda menu: (category_order.get(menu["cat"], 999), menu["name"]))
        for menu in menus:
            if _service_menu_allowed(menu):
                category = category_names.get(menu["cat"], menu["cat"])
                display_name = SERVICE_MENU_NAMES.get(menu["id"], menu["name"])
                choices.append({"id": menu["id"], "name": display_name, "category": category,
                                "label": f"[{category}] {display_name}",
                                "emoji": _menu_emoji(display_name, menu.get("emoji", ""))})
        return [{"id": None, "name": "전체 메뉴", "category": "할인", "label": ALL_MENU_LABEL, "emoji": "🎟️"}, *choices]

    def roulette_table(self) -> pd.DataFrame:
        """룰렛 칸 목록 → 편집용 표. 서버의 칸 모양은 user/menu_data.py 의 ROULETTE_PRIZES 와 같다."""
        choices = {choice["id"]: choice for choice in self.roulette_menu_choices() if choice["id"]}
        rows = []
        for p in self.backend.roulette_prizes():
            free = p["kind"] == "free"
            choice = choices.get(p.get("item_id"))
            rows.append({"서비스 메뉴": choice["label"] if free and choice else ALL_MENU_LABEL,
                         "종류": ROULETTE_KINDS[p["kind"]], "할인율(%)": 5 if free else int(p.get("percent", 5)),
                         "확률 가중치": float(p.get("weight", 1)), "색상": p.get("color", "#888888")})
        return pd.DataFrame(rows, columns=ROULETTE_COLUMNS)

    @staticmethod
    def roulette_odds(table: pd.DataFrame) -> list[float]:
        """칸별 당첨 확률(%). 가중치 합이 0 이면 모두 같은 확률로 본다 (손님 화면과 같은 규칙)."""
        w = [max(float(v), 0) if pd.notna(v) else 0.0 for v in table["확률 가중치"]]
        total = sum(w)
        return [round(100 * x / total, 1) for x in w] if total else [round(100 / len(w), 1)] * len(w) if w else []

    def save_roulette(self, table: pd.DataFrame) -> None:
        """편집한 표를 검사해 서버 칸 모양으로 바꿔 통째로 저장한다."""
        choices = {choice["label"]: choice for choice in self.roulette_menu_choices() if choice["id"]}
        prizes = []
        for n, row in enumerate(table.to_dict("records"), 1):
            kind = {v: k for k, v in ROULETTE_KINDS.items()}.get(row["종류"])
            if kind is None:
                raise CategoryError(f"{n}번째 칸의 종류(할인/서비스)를 골라 주세요.")
            color = _text(row["색상"]).strip()
            if not _HEX.match(color):
                raise CategoryError(f"{n}번째 칸의 색상은 #RRGGBB 형식이어야 해요.")
            weight = row["확률 가중치"]
            if pd.isna(weight) or weight < 0:
                raise CategoryError(f"{n}번째 칸의 확률 가중치는 0 이상이어야 해요.")
            prize = {"color": color, "kind": kind, "weight": float(weight)}
            if kind == "discount":
                if row["서비스 메뉴"] != ALL_MENU_LABEL:
                    raise CategoryError(f"{n}번째 할인 칸은 전체 메뉴를 골라 주세요.")
                percent = row["할인율(%)"]
                if pd.isna(percent) or int(percent) not in (5, 10, 15, 20):
                    raise CategoryError(f"{n}번째 칸의 할인율은 5·10·15·20% 중에서 골라 주세요.")
                prize.update(percent=int(percent), emoji="🎟️", label=f"모든 메뉴<br><b>{int(percent)}% 할인</b>")
                default_short = f"전 메뉴 {int(percent)}% 할인"
            else:
                menu = _text(row["서비스 메뉴"])
                if menu not in choices:
                    raise CategoryError(f"{n}번째 칸의 서비스 메뉴를 골라 주세요.")
                choice = choices[menu]
                prize.update(item_id=choice["id"], emoji=choice["emoji"], label=f"{escape(choice['name'])}<br><b>서비스</b>")
                default_short = f"{choice['name']} 서비스"
            prize["short"] = default_short
            prizes.append(prize)
        if not ROULETTE_MIN_SLOTS <= len(prizes) <= ROULETTE_MAX_SLOTS:
            raise CategoryError(f"룰렛 칸은 {ROULETTE_MIN_SLOTS}~{ROULETTE_MAX_SLOTS}개여야 해요.")
        weights = [p["weight"] for p in prizes]
        if any(weight % 10 for weight in weights) or sum(weights) != 100:
            raise CategoryError("확률은 10% 단위로 고르고 전체 합계를 100%로 맞춰 주세요.")
        self.backend.save_roulette_prizes(prizes)

    # ---- 고객 / 주문 / 통계 ----
    def regular_preferences(self) -> list[dict]:
        """마케팅 AI 추천에서 쓸 실제 DB의 오늘 주문한 2회 이상 방문 고객을 읽는다."""
        # 더미는 admin_dummy_data의 1,000명 주문으로 시연하고, API 모드는 아래 DB 경로를 그대로 읽는다.
        # 실제 DB 연결: backend/app/stores/customer_notes.py -> members/orders/order_items/menus
        if self.source != "api":
            return self.backend.regular_preferences()
        return api.get("/admin/api/marketing/regular-preferences", self.backend.token)["preferences"]

    def customer_grades(self, rule: dict | None = None) -> dict:
        """화면에서 다시 세지 않고 백엔드가 집계한 등급별 인원을 사용한다."""
        return self.backend.customer_grades(rule if rule is not None else self.customer_grade_rules())

    def customer_grade_rules(self) -> dict:
        """더미·API 여부와 관계없이 현재 기본 기준을 가져온다."""
        return self.backend.customer_grade_rules()

    def save_customer_grade_rules(self, rule: dict) -> dict:
        """더미 화면에서 실제 DB에 저장됐다고 오해하지 않도록 막는다."""
        if self.source != "api":
            raise Unsupported("기준 저장은 서버에 연결한 화면에서 사용할 수 있어요.")
        return self.backend.save_customer_grade_rules(rule)

    def members(self, rule: dict | None = None) -> pd.DataFrame:
        rows = self.backend.members(rule if rule is not None else self.customer_grade_rules())["members"]
        return pd.DataFrame([{
            "customer_id": m["id"], "닉네임": m["nickname"], "성별": m["gender"], "연령대": m["age_group"],
            "생일": m.get("birthday"), "방문 횟수": m["visit_count"], "마지막 방문일": _kst_date(m["last_visit_at"]),
            # 문자 발송 가능 수는 동의 여부뿐 아니라 실제 전화번호 보유 여부까지 확인해야 한다.
            "전화번호 보유": m.get("has_phone", False), "마케팅 수신 동의": m["marketing_consent"],
            "수신거부": m["opted_out"], "등급": m["grade"]} for m in rows],
            columns=["customer_id", "닉네임", "성별", "연령대", "생일", "방문 횟수", "마지막 방문일", "전화번호 보유",
                     "마케팅 수신 동의", "수신거부", "등급"])

    def orders(self) -> pd.DataFrame:
        rows = self.backend.orders()
        return pd.DataFrame([{
            "order_id": f"O{o['id']:04d}", "주문 시각": datetime.fromisoformat(o["ts"]).astimezone(KST).replace(tzinfo=None),
            "customer_id": o["member_id"], "닉네임": o.get("nickname") or "비회원", "테이블": o["table_no"],
            "주문 내역": ", ".join(f"{l['name']} x{l['qty']}" for l in o["lines"]), "금액": o["total"],
            "AI 추천 사용": o["ai_combo"]} for o in rows],
            columns=["order_id", "주문 시각", "customer_id", "닉네임", "테이블", "주문 내역", "금액", "AI 추천 사용"])

    def stats(self, rule: dict | None = None) -> dict:
        return self.backend.stats(rule if rule is not None else self.customer_grade_rules())

    def sales_insights(self, rule: dict | None = None) -> dict:
        """실제 서버의 추가 통계를 읽고, 더미 모드에서는 기존 화면 계산을 유지한다."""
        if self.source == "api":
            return self.backend.sales_insights(rule if rule is not None else self.customer_grade_rules())
        from dashboard_stats import summarize

        return summarize(self.orders(), self.members(rule), tables=self.store()["tables"])

    def menu_alerts(self) -> dict:
        """API 모드는 DB 품절 알림을, 더미 모드는 기존 시연용 메뉴를 표시한다."""
        if self.source == "api":
            alerts = self.backend.menu_alerts()
            return {"sold_out": [alert["name"] for alert in alerts],
                    "popular_sold_out": [alert["name"] for alert in alerts if alert["popular"]]}
        from dashboard_stats import menu_alerts

        return menu_alerts(self.menus(), self.stats()["popular_menus"])

    def opportunities(self, round_no: int = 0) -> dict:
        """API·더미 백엔드에서 같은 추천 페이지 응답을 받는다."""
        return self.backend.opportunities(round_no)

    def growth_performance(self, rule: dict | None = None) -> dict:
        """API는 DB 계산 결과를, 더미는 같은 공식의 화면 계산 결과를 사용한다."""
        if self.source == "api":
            return self.backend.growth_performance()
        # 순환 import를 피하려고 더미 화면에서 호출할 때만 계산 함수를 가져온다.
        from admin.views.growth_performance import growth_summary
        return growth_summary(self.orders(), self.members(rule))

    # ---- 직원 호출 ----
    def calls(self) -> list[dict]:
        return self.backend.calls()

    def call_done(self, call_id: int) -> dict:
        return self.backend.call_done(call_id)

    # ---- 마케팅 (서버 필요) ----
    def __getattr__(self, name):  # sms_*, chat_*, opt_out 은 백엔드로 위임
        if name.startswith(("sms_", "chat_")) or name == "opt_out":
            return getattr(self.backend, name)
        raise AttributeError(name)


def _text(value) -> str:
    """표의 빈 칸(None/NaN)은 빈 문자열로 보낸다. (NaN 은 JSON 으로 보낼 수 없다)"""
    return "" if value is None or pd.isna(value) else str(value)


def _kst_date(iso: str | None):
    return datetime.fromisoformat(iso).astimezone(KST).date() if iso else None


def data_source_mode() -> str:
    mode = os.getenv("DATA_SOURCE", "auto").strip().lower()
    return mode if mode in MODES else "auto"


def skip_token_login() -> bool:
    """APP_ENV=dev 이고 ADMIN_SKIP_TOKEN (기본 켜짐) 이면 토큰 입력 화면 없이 ADMIN_TOKEN 으로 자동 로그인한다.

    APP_ENV 가 dev 가 아니면(운영·미설정) 항상 토큰 입력 화면을 거친다.
    dev 에서도 ADMIN_SKIP_TOKEN=0/false/no/off 로 바꾸면 토큰 입력 화면이 다시 나온다.
    """
    if not api.is_dev():  # 개발 환경이 아니면 우회하지 않는다
        return False
    return os.getenv("ADMIN_SKIP_TOKEN", "1").strip().lower() not in {"0", "false", "no", "off"}


def default_admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "change-me")


class LoginResult:
    def __init__(self, repo=None, error: str | None = None, notice: str | None = None):
        self.repo, self.error, self.notice = repo, error, notice


def connect(token: str) -> LoginResult:
    """DATA_SOURCE 에 맞게 토큰을 확인하고 저장소를 만든다."""
    mode = data_source_mode()
    dummy = AdminRepository(DummyBackend())
    if mode == "dummy":
        return LoginResult(dummy) if dummy.backend.login(token) else LoginResult(error="토큰이 올바르지 않습니다.")
    backend = ApiBackend(token)
    try:
        if backend.login(token):
            return LoginResult(AdminRepository(backend))
        return LoginResult(error="토큰이 올바르지 않습니다.")
    except api.ApiUnavailable:
        if mode == "api":
            return LoginResult(error="서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.")
    # auto: 서버가 없으면 더미로 연다
    if not dummy.backend.login(token):
        return LoginResult(error="토큰이 올바르지 않습니다.")
    return LoginResult(dummy, notice="서버에 연결할 수 없어 더미 데이터로 표시하고 있어요.")
