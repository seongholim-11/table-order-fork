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
from html import escape, unescape
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from admin_dummy_data import GRADES, DummyBackend  # noqa: E402, F401  (GRADES 는 화면에서 여기서 가져간다)
from shared import api  # noqa: E402

ENDPOINTS = {
    "store": "/api/v1/store",
    "menus": "/admin/api/menus",              # GET {categories, menus} / PUT·DELETE /{id}
    "roulette": "/api/content/roulette_prizes",  # GET 칸 목록 / PUT /admin/api/content/roulette_prizes 통째로 교체
    "categories": "/api/content/categories",  # GET 전체 목록(가상 카테고리 포함) / PUT /admin/api/content/categories 통째로 교체
    "members": "/admin/api/members",          # GET ?repeat&regular&dormant
    "orders": "/admin/api/orders",
    "stats": "/admin/api/stats",
    "sms": "/admin/api/marketing/sms",        # /usage /preview /send /logs
    "opt_out": "/admin/api/members/{id}/opt-out",
}
KST = timezone(timedelta(hours=9))
SPICY_LABELS = {0: "안 매움", 1: "순한맛", 2: "보통맛", 3: "아주 매움"}
SPICY_VALUES = {v: k for k, v in SPICY_LABELS.items()}
MODES = ("dummy", "api", "auto")
DEFAULT_RULE = {"repeat": 2, "regular": 5, "dormant": 60}
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
        return api.get(ENDPOINTS["categories"])

    def save_categories(self, categories):
        return api.put("/admin/api/content/categories", self.token, json=categories)

    def roulette_prizes(self):
        return api.get(ENDPOINTS["roulette"])

    def save_roulette_prizes(self, prizes):
        return api.put("/admin/api/content/roulette_prizes", self.token, json=prizes)

    def save_menu(self, menu_id, fields):
        return api.put(f"{ENDPOINTS['menus']}/{menu_id}", self.token, json=fields)

    def delete_menu(self, menu_id):
        return api.delete(f"{ENDPOINTS['menus']}/{menu_id}", self.token)

    def members(self, rule):
        return api.get(ENDPOINTS["members"], self.token, params=rule)

    def orders(self):
        return api.get(ENDPOINTS["orders"], self.token)

    def stats(self, rule):
        return api.get(ENDPOINTS["stats"], self.token)

    def sms_usage(self):
        return api.get(f"{ENDPOINTS['sms']}/usage", self.token)

    def sms_preview(self, grades, body, scheduled_at=None, member_ids=None):
        return api.post(f"{ENDPOINTS['sms']}/preview", self.token, json=_sms_body(grades, body, scheduled_at, member_ids))

    def sms_send(self, grades, body, scheduled_at=None, member_ids=None):
        return api.post(f"{ENDPOINTS['sms']}/send", self.token, json=_sms_body(grades, body, scheduled_at, member_ids))

    def sms_cancel(self, log_id):
        return api.post(f"{ENDPOINTS['sms']}/logs/{log_id}/cancel", self.token)

    def sms_logs(self):
        return api.get(f"{ENDPOINTS['sms']}/logs", self.token)

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
ROULETTE_COLUMNS = ["칸 문구", "이모지", "종류", "할인율(%)", "서비스 메뉴", "색상", "확률 가중치", "당첨 안내문"]
ROULETTE_KINDS = {"discount": "할인", "free": "서비스"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class CategoryError(Exception):
    """카테고리 이름 중복·빈 이름·메뉴가 남은 카테고리 삭제 같은 입력 문제 (화면에 그대로 보여줄 수 있는 메시지)."""


class AdminRepository:
    """백엔드 JSON → 화면용 표/값. 더미든 서버든 같은 변환을 쓴다."""

    def __init__(self, backend):
        self.backend = backend

    @property
    def source(self) -> str:
        return self.backend.source

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
        counts: dict[str, int] = {}
        for m in self.backend.menus()["menus"]:
            counts[m["cat"]] = counts.get(m["cat"], 0) + 1
        return [{**c, "menu_count": counts.get(c["id"], 0)} for c in self.backend.categories_full()
                if c["id"] not in VIRTUAL_CATEGORIES]

    def _save_categories(self, mutate) -> None:
        """전체 목록(가상 카테고리 포함)을 읽어 고친 뒤 통째로 저장한다. 가상 카테고리는 건드리지 않는다."""
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

        def add(full):
            full.append({"id": new_id, "icon": (icon or "").strip() or ICON_DEFAULT,
                         "name": self._clean_name(name, full), "colors": COLOR_PRESETS.get(color, COLOR_PRESETS["보라"])})
        self._save_categories(add)
        return new_id

    def update_category(self, category_id: str, name: str, icon: str, color: str | None = None) -> None:
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

        def remove(full):
            full[:] = [c for c in full if c["id"] != category_id]
        self._save_categories(remove)

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
        saved, seen = 0, set()
        for row in new.to_dict("records"):
            menu_id = row["id"] if isinstance(row["id"], str) and row["id"] else f"m{uuid.uuid4().hex[:6]}"
            seen.add(menu_id)
            if old_by_id.get(menu_id) == {**row, "id": menu_id}:
                continue  # 바뀌지 않은 행
            self.backend.save_menu(menu_id, {
                "name": row["메뉴명"], "cat": ids[row["카테고리"]], "price": int(row["가격"]), "desc": _text(row["설명"]),
                "image_url": _text(row["이미지 URL"]), "soldout": not bool(row["판매 여부"]),
                "spicy": SPICY_VALUES.get(row["매운 정도"], 0), "weight": int(row["추천 가중치"]),
                "set_ok": bool(row["세트 가능"])})
            saved += 1
        deleted = [i for i in old_by_id if i not in seen]
        for menu_id in deleted:
            self.backend.delete_menu(menu_id)
        return {"saved": saved, "deleted": len(deleted)}

    # ---- 이벤트: 룰렛 ----
    def roulette_table(self) -> pd.DataFrame:
        """룰렛 칸 목록 → 편집용 표. 서버의 칸 모양은 user/menu_data.py 의 ROULETTE_PRIZES 와 같다."""
        names = {m["id"]: m["name"] for m in self.backend.menus()["menus"]}
        rows = []
        for p in self.backend.roulette_prizes():
            free = p["kind"] == "free"
            rows.append({"칸 문구": unescape(re.sub(r"<[^>]+>", "", p["label"].split("<br>")[0])), "이모지": p.get("emoji", ""),
                         "종류": ROULETTE_KINDS[p["kind"]], "할인율(%)": 0 if free else int(p.get("percent", 0)),
                         "서비스 메뉴": names.get(p.get("item_id"), p.get("item_id")) if free else None,
                         "색상": p.get("color", "#888888"), "확률 가중치": p.get("weight", 1), "당첨 안내문": p.get("short", "")})
        return pd.DataFrame(rows, columns=ROULETTE_COLUMNS)

    @staticmethod
    def roulette_odds(table: pd.DataFrame) -> list[float]:
        """칸별 당첨 확률(%). 가중치 합이 0 이면 모두 같은 확률로 본다 (손님 화면과 같은 규칙)."""
        w = [max(float(v), 0) if pd.notna(v) else 0.0 for v in table["확률 가중치"]]
        total = sum(w)
        return [round(100 * x / total, 1) for x in w] if total else [round(100 / len(w), 1)] * len(w) if w else []

    def save_roulette(self, table: pd.DataFrame) -> None:
        """편집한 표를 검사해 서버 칸 모양으로 바꿔 통째로 저장한다."""
        ids = {m["name"]: m["id"] for m in self.backend.menus()["menus"]}
        prizes = []
        for n, row in enumerate(table.to_dict("records"), 1):
            line1, kind = _text(row["칸 문구"]).strip(), {v: k for k, v in ROULETTE_KINDS.items()}.get(row["종류"])
            if not line1:
                raise CategoryError(f"{n}번째 칸의 문구를 입력해 주세요.")
            if kind is None:
                raise CategoryError(f"{n}번째 칸의 종류(할인/서비스)를 골라 주세요.")
            color = _text(row["색상"]).strip()
            if not _HEX.match(color):
                raise CategoryError(f"{n}번째 칸의 색상은 #RRGGBB 형식이어야 해요.")
            weight = row["확률 가중치"]
            if pd.isna(weight) or weight < 0:
                raise CategoryError(f"{n}번째 칸의 확률 가중치는 0 이상이어야 해요.")
            prize = {"emoji": _text(row["이모지"]).strip() or "🎁", "color": color, "kind": kind, "weight": float(weight)}
            if kind == "discount":
                percent = row["할인율(%)"]
                if pd.isna(percent) or not 1 <= percent <= 100:
                    raise CategoryError(f"{n}번째 칸의 할인율은 1~100% 여야 해요.")
                prize.update(percent=int(percent), label=f"{escape(line1)}<br><b>{int(percent)}% 할인</b>")
                default_short = f"{line1} {int(percent)}% 할인"
            else:
                menu = _text(row["서비스 메뉴"])
                if menu not in ids:
                    raise CategoryError(f"{n}번째 칸의 서비스 메뉴를 골라 주세요.")
                prize.update(item_id=ids[menu], label=f"{escape(line1)}<br><b>서비스</b>")
                default_short = f"{menu} 서비스"
            prize["short"] = _text(row["당첨 안내문"]).strip() or default_short
            prizes.append(prize)
        if not ROULETTE_MIN_SLOTS <= len(prizes) <= ROULETTE_MAX_SLOTS:
            raise CategoryError(f"룰렛 칸은 {ROULETTE_MIN_SLOTS}~{ROULETTE_MAX_SLOTS}개여야 해요.")
        if not any(p["weight"] > 0 for p in prizes):
            raise CategoryError("확률 가중치가 0보다 큰 칸이 하나는 있어야 해요.")
        self.backend.save_roulette_prizes(prizes)

    # ---- 고객 / 주문 / 통계 ----
    def members(self, rule: dict | None = None) -> pd.DataFrame:
        rows = self.backend.members(rule or DEFAULT_RULE)["members"]
        return pd.DataFrame([{
            "customer_id": m["id"], "닉네임": m["nickname"], "성별": m["gender"], "연령대": m["age_group"],
            "방문 횟수": m["visit_count"], "마지막 방문일": _kst_date(m["last_visit_at"]),
            "마케팅 수신 동의": m["marketing_consent"], "수신거부": m["opted_out"], "등급": m["grade"]} for m in rows],
            columns=["customer_id", "닉네임", "성별", "연령대", "방문 횟수", "마지막 방문일", "마케팅 수신 동의", "수신거부", "등급"])

    def orders(self) -> pd.DataFrame:
        rows = self.backend.orders()
        return pd.DataFrame([{
            "order_id": f"O{o['id']:04d}", "주문 시각": datetime.fromisoformat(o["ts"]).astimezone(KST).replace(tzinfo=None),
            "customer_id": o["member_id"], "닉네임": o.get("nickname") or "비회원", "테이블": o["table_no"],
            "주문 내역": ", ".join(f"{l['name']} x{l['qty']}" for l in o["lines"]), "금액": o["total"],
            "AI 추천 사용": o["ai_combo"]} for o in rows],
            columns=["order_id", "주문 시각", "customer_id", "닉네임", "테이블", "주문 내역", "금액", "AI 추천 사용"])

    def stats(self, rule: dict | None = None) -> dict:
        return self.backend.stats(rule or DEFAULT_RULE)

    # ---- 마케팅 (서버 필요) ----
    def __getattr__(self, name):  # sms_usage, sms_preview, sms_send, sms_logs, opt_out 은 백엔드로 위임
        if name.startswith("sms_") or name == "opt_out":
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
