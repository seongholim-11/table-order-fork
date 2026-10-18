"""관리자 화면용 더미 데이터 — '서버와 똑같은 JSON'을 돌려주는 가짜 서버(DummyBackend).

반환 모양은 백엔드 /admin/api/* 응답과 같다. 그래서 화면과 변환 코드(admin_repository.py)는
데이터가 더미인지 서버인지 모르고, DATA_SOURCE 만 바꾸면 전환된다.
"""
import copy
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from user import menu_data  # noqa: E402

TODAY = date(2026, 10, 12)
GRADES = ["신규", "재방문", "단골", "휴면"]  # admin_repository 도 여기 것을 가져다 쓴다
AGE_GROUPS = ["20대", "30대", "40대", "50대 이상"]
DUMMY_ORDER_COUNT = 1000  # 매출 추이와 회원·비회원 비교가 충분히 보이도록 한 달 주문량을 넉넉히 만든다.
DUMMY_TODAY_ORDER_COUNT = 80

# 손님 화면(user/menu_data.py)과 같은 카테고리. 서버에는 AI 추천 조합·인기메뉴 같은 가상 카테고리도 섞여 있으나 관리자 더미는 실제 카테고리만 쓴다.
CATEGORIES = [c for c in menu_data.CATEGORIES if c["id"] not in ("ai", "best")]


def _menu(id_, cat, name, price, spicy=0, soldout=False, weight=50, set_ok=True, desc=""):
    return {"id": id_, "cat": cat, "name": name, "desc": desc, "price": price, "emoji": "🍽️", "tags": [],
            "soldout": soldout, "spicy": spicy, "weight": weight, "set_ok": set_ok, "image_url": ""}


MENUS = [
    _menu("c1", "chicken", "역전 옛날통닭 (한 마리·후라이드)", 18000, desc="겉은 바삭, 속은 촉촉한 가마솥 통닭"),
    _menu("c2", "chicken", "간장마늘 치킨", 20000, desc="달콤짭짤 간장에 마늘 듬뿍"),
    _menu("c3", "chicken", "닭똥집 튀김", 11000, desc="쫄깃한 식감, 맥주 도둑"),
    _menu("a1", "anju", "먹태구이", 14000, desc="청양마요 소스와 함께"),
    _menu("a2", "anju", "골뱅이 소면 무침 (보통맛)", 17000, spicy=2),
    _menu("a3", "anju", "직화 무뼈닭발 (아주 매운맛)", 18000, spicy=3),
    _menu("a4", "anju", "계란말이", 10000),
    _menu("a11", "anju", "노가리 구이", 9000, soldout=True),
    _menu("s1", "soup", "나가사키 짬뽕탕", 16000, spicy=2),
    _menu("s2", "soup", "어묵탕", 12000),
    _menu("b1", "beer", "생맥주 500cc", 4500, set_ok=False),
    _menu("j1", "soju", "참이슬", 5000, set_ok=False),
    _menu("d1", "side", "콜라", 2000, set_ok=False),
    _menu("d7", "side", "라면", 4000, set_ok=False),
    _menu("d8", "side", "짜장라면", 4500, set_ok=False),
]

# 손님 화면과 같은 룰렛 칸에 관리자용 확률 가중치(weight)를 더한다.
ROULETTE_PRIZES = [{**p, "weight": 50 if i == 0 else 10} for i, p in enumerate(menu_data.ROULETTE_PRIZES)]


class Unsupported(Exception):
    """더미 모드에서는 쓸 수 없는 기능 (예: 실제 문자 발송)."""


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def _grade(visits: int, last: date, rule: dict) -> str:
    if (TODAY - last).days >= rule["dormant"]:
        return "휴면"
    return "단골" if visits >= rule["regular"] else "재방문" if visits >= rule["repeat"] else "신규"


def _age_group(year: int) -> str:
    age = TODAY.year - year
    # 화면에는 20대 미만 구간을 두지 않으므로 최저 연령 구간은 20대로 합친다.
    return "20대" if age < 30 else "30대" if age < 40 else "40대" if age < 50 else "50대 이상"


class DummyBackend:
    """서버(ApiBackend)와 같은 메서드·같은 JSON. 상태는 이 객체(= 화면 세션) 안에만 있다."""
    source = "dummy"

    def __init__(self, seed: int = 7):
        r = random.Random(seed)
        self.menus_ = [dict(m) for m in MENUS]
        self.categories_ = [dict(c) for c in CATEGORIES]
        self.roulette_ = copy.deepcopy(ROULETTE_PRIZES)
        self.members_ = []
        for i in range(1, 61):
            self.members_.append({
                "id": i, "nickname": f"손님{i:02d}", "gender": r.choice(["남", "여"]),
                # 기존 20대 미만 더미 고객은 성인 연령대 네 구간에 고르게 다시 분산한다.
                # 주문이 이 회원 id와 연결되므로 회원별 주문·매출도 같은 연령대로 자동 귀속된다.
                "birth_year": r.choice([2002, 1995, 1986, 1974]),
                "visit_count": r.choice([1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 12]),
                "last_visit": TODAY - timedelta(days=r.choice([0, 1, 2, 3, 5, 8, 14, 21, 35, 50, 70, 95, 130])),
                "marketing_consent": r.random() < 0.7, "opted_out": False})
        self.orders_ = []
        for i in range(1, DUMMY_ORDER_COUNT + 1):
            picks = r.sample([m for m in MENUS if not m["soldout"]], r.randint(2, 4))
            lines = [{"id": m["id"], "name": m["name"], "opt": "", "unit": m["price"], "qty": r.randint(1, 2)} for m in picks]
            day = TODAY - timedelta(days=0 if i <= DUMMY_TODAY_ORDER_COUNT else r.randint(1, 29))
            ts = datetime(day.year, day.month, day.day, tzinfo=timezone(timedelta(hours=9))) + timedelta(minutes=r.randint(1020, 1430))
            # 실제 매장처럼 로그인한 회원 주문과 로그인하지 않은 비회원 주문을 함께 만든다.
            # 고정 시드를 쓰므로 화면과 테스트에서는 매번 같은 약 75%의 회원 주문 비율이 나온다.
            member_id = r.choice(self.members_)["id"] if r.random() < 0.75 else None
            # 성과 화면에서 도입 전후를 비교할 수 있도록 더미 AI 마케팅은 최근 14일부터 시작한 것으로 둔다.
            ai_adopted = day >= TODAY - timedelta(days=14)
            self.orders_.append({"id": i, "ts": _iso(ts), "table_no": r.randint(1, 30), "member_id": member_id,
                                 "lines": lines, "total": sum(l["unit"] * l["qty"] for l in lines),
                                 "ai_combo": ai_adopted and r.random() < 0.45,
                                 "roulette_discount_percent": 0, "recommendation_event_id": None})
        self.orders_.sort(key=lambda o: o["ts"], reverse=True)
        # 직원 호출 화면을 서버 없이 먼저 확인할 수 있도록 대기/완료 호출을 함께 준비한다.
        # 실제 API도 같은 필드(id, table_no, items, ts, done)를 반환하면 화면 코드는 바꿀 필요가 없다.
        call_specs = [
            (1, 7, ["물", "수저 2개"], 4, False),
            (2, 12, ["앞접시 3개"], 7, False),
            (3, 3, ["직원 호출"], 11, False),
            (4, 21, ["물티슈", "물"], 18, True),
            (5, 9, ["소주잔 2개"], 26, True),
        ]
        call_base = datetime(TODAY.year, TODAY.month, TODAY.day, 21, 30, tzinfo=timezone(timedelta(hours=9)))
        self.calls_ = [{"id": call_id, "table_no": table_no, "items": items,
                        "ts": _iso(call_base - timedelta(minutes=minutes_ago)), "done": done}
                       for call_id, table_no, items, minutes_ago, done in call_specs]

    # ---- 로그인 / 매장 -----------------------------------------------------
    def login(self, token: str) -> bool:
        import os
        return token == os.getenv("ADMIN_TOKEN", "change-me")

    def store(self) -> dict:
        return {"name": "역전할머니맥주", "branch": "홍대점", "slogan": "", "tables": 30}

    # ---- 메뉴 ----------------------------------------------------------------
    def menus(self) -> dict:
        return {"categories": [{"id": c["id"], "name": c["name"]} for c in self.categories_],
                "menus": [dict(m) for m in self.menus_]}

    def categories_full(self) -> list:
        return [dict(c) for c in self.categories_]

    def save_categories(self, categories: list) -> list:
        self.categories_ = [dict(c) for c in categories]
        return self.categories_full()

    def roulette_prizes(self) -> list:
        return copy.deepcopy(self.roulette_)

    def save_roulette_prizes(self, prizes: list) -> list:
        self.roulette_ = copy.deepcopy(prizes)
        return self.roulette_prizes()

    def save_menu(self, menu_id: str, fields: dict) -> dict:
        cur = next((m for m in self.menus_ if m["id"] == menu_id), None)
        if cur is None:
            cur = _menu(menu_id, fields["cat"], fields["name"], fields["price"])
            self.menus_.append(cur)
        cur.update(fields)
        return dict(cur)

    def delete_menu(self, menu_id: str) -> None:
        self.menus_ = [m for m in self.menus_ if m["id"] != menu_id]

    # ---- 고객 / 주문 / 통계 --------------------------------------------------------
    def customer_grades(self, rule: dict) -> dict:
        """서버 없이도 새 API와 같은 응답 모양으로 고객 등급 화면을 확인한다."""
        counts = {grade: 0 for grade in GRADES}
        for member in self.members(rule)["members"]:
            counts[member["grade"]] += 1
        return {**counts, "dormant_count": counts["휴면"]}

    def customer_grade_rules(self) -> dict:
        """더미 모드에서 사용하는 기본 등급 기준. 서버 설정을 읽거나 저장하지 않는다."""
        return {"repeat": 2, "regular": 5, "dormant": 30}

    def members(self, rule: dict) -> dict:
        return {"rule": rule, "members": [{
            "id": m["id"], "nickname": m["nickname"], "gender": m["gender"], "age_group": _age_group(m["birth_year"]),
            "visit_count": m["visit_count"], "last_visit_at": _iso(datetime.combine(m["last_visit"], datetime.min.time(), timezone.utc)),
            "marketing_consent": m["marketing_consent"], "opted_out": m["opted_out"], "has_phone": m["marketing_consent"],
            "grade": _grade(m["visit_count"], m["last_visit"], rule)} for m in self.members_]}

    def orders(self) -> list:
        nick = {m["id"]: m["nickname"] for m in self.members_}
        return [{**o, "nickname": nick.get(o["member_id"])} for o in self.orders_]

    # ---- 직원 호출 ------------------------------------------------------------
    def calls(self) -> list:
        """최신 호출부터 반환한다. 대기/완료 구분과 정렬은 화면에서도 한 번 더 보장한다."""
        return [dict(call) for call in sorted(self.calls_, key=lambda call: call["ts"], reverse=True)]

    def call_done(self, call_id: int) -> dict:
        call = next((call for call in self.calls_ if call["id"] == call_id), None)
        if call is None:
            raise Unsupported("직원 호출을 찾을 수 없습니다.")
        call["done"] = True
        return dict(call)

    def stats(self, rule: dict) -> dict:
        today = [o for o in self.orders_ if o["ts"][:10] >= TODAY.isoformat()]  # UTC 기준 근사
        members = {m["id"]: m for m in self.members(rule)["members"]}
        # 비회원 주문에는 member_id가 없으므로 신규·재방문 고객 집계에서 제외한다.
        grades = {o["member_id"]: members[o["member_id"]]["grade"] for o in today if o["member_id"] in members}
        counts: dict[str, int] = {}
        for o in self.orders_:
            for l in o["lines"]:
                counts[l["name"]] = counts.get(l["name"], 0) + l["qty"]
        ai = sum(1 for o in self.orders_ if o["ai_combo"])
        shown = len(self.orders_) * 2  # 더미: 추천 노출 수
        age: dict[str, int] = {k: 0 for k in AGE_GROUPS}
        gender: dict[str, int] = {}
        for m in members.values():
            age[m["age_group"]] += 1
            gender[m["gender"]] = gender.get(m["gender"], 0) + 1
        return {"today_orders": len(today), "avg_order_amount": int(sum(o["total"] for o in today) / len(today)) if today else 0,
                "new_customers": sum(1 for g in grades.values() if g == "신규"),
                "returning_customers": sum(1 for g in grades.values() if g in ("재방문", "단골")),
                "age_groups": age, "genders": gender,
                "popular_menus": [{"name": n, "qty": q} for n, q in sorted(counts.items(), key=lambda kv: -kv[1])[:10]],
                "ai": {"recommendations": shown, "ai_orders": ai, "hit_rate": round(ai / shown, 3),
                       "definition": "AI 조합이 포함된 주문 수 / 추천이 노출된 횟수 (임시 기준)"}}

    def opportunities(self, round_no: int = 0) -> dict:
        """서버가 없어도 기존 화면 규칙으로 같은 추천 응답 모양을 만든다."""
        # 실행 시점에 가져와 admin_repository와의 순환 import를 피한다.
        from admin.marketing.context import build_marketing_context
        from admin.marketing.recommendations import pick_recommendations, recommend
        from admin_repository import AdminRepository

        cards, page, pages = pick_recommendations(
            recommend(build_marketing_context(AdminRepository(self), self.customer_grade_rules())), round_no)
        return {"items": cards, "page": page, "pages": pages}

    # ---- 문자 발송: 서버 SmsService 와 같은 규칙·같은 JSON 으로 흉내만 낸다 (실제 전송 없음) ----------------------
    SMS_LIMIT = {"SMS": 100, "LMS": 20}
    STORE_NAME = "역전할머니맥주"
    OPT_OUT_NUMBER = "080-000-0000"
    GRADE_RULE = {"repeat": 2, "regular": 5, "dormant": 30}

    def _seed_sms_logs(self):
        """화면이 비어 보이지 않도록 이번 달 발송 기록 몇 건을 미리 넣어 둔다."""
        month = TODAY.strftime("%Y-%m")
        kst = timezone(timedelta(hours=9))
        rows = [(2, "SMS", "휴면 고객 재방문 이벤트", 14, "dry_run", None), (4, "SMS", "신메뉴 먹태구이 출시 안내", 9, "dry_run", None),
                (7, "LMS", "추석 연휴 영업시간 안내와 단골 감사 쿠폰 발행 소식을 알려드립니다. 방문 시 쿠폰을 보여주세요.", 6, "dry_run", None),
                (9, "SMS", "주말 생맥주 1+1 이벤트", 12, "failed", "HTTP 401 인증 오류 (더미)"),
                (10, "SMS", "금요일 단골 안주 10% 할인", 15, "dry_run", None)]
        self.sms_logs_ = [{"id": i, "ts": _iso(datetime(TODAY.year, TODAY.month, day, 15, 30, tzinfo=kst)), "month": month,
                           "request_id": None if status == "failed" else f"dryrun-seed{i:04d}", "type": kind,
                           "content": f"(광고){self.STORE_NAME}\n{text}\n무료수신거부 {self.OPT_OUT_NUMBER}",
                           "target_count": n, "status": status, "error": err}
                          for i, (day, kind, text, n, status, err) in enumerate(rows, 1)]
        self.sms_logs_.reverse()  # 서버처럼 최신 기록이 먼저

    def _sms_targets(self, grades, member_ids=None):
        return [m for m in self.members_ if m["marketing_consent"] and not m["opted_out"]
                and _grade(m["visit_count"], m["last_visit"], self.GRADE_RULE) in grades
                and (member_ids is None or m["id"] in member_ids)]

    def sms_usage(self) -> dict:
        if not hasattr(self, "sms_logs_"):
            self._seed_sms_logs()
        used = {"SMS": 0, "LMS": 0}
        for log in self.sms_logs_:
            if log["status"] in ("sent", "dry_run", "scheduled"):
                used[log["type"]] += log["target_count"]
        return {"month": TODAY.strftime("%Y-%m"), "used": used, "limit": dict(self.SMS_LIMIT)}

    def sms_preview(self, grades: list, body: str, scheduled_at=None, member_ids=None) -> dict:
        text = f"(광고){self.STORE_NAME}\n{body.strip()}\n무료수신거부 {self.OPT_OUT_NUMBER}"
        size = sum(1 if ord(ch) < 128 else 2 for ch in text)
        kind = "SMS" if size <= 90 else "LMS"
        usage = self.sms_usage()
        remaining = usage["limit"][kind] - usage["used"][kind]
        targets = self._sms_targets(grades, member_ids)
        problems = []
        if not body.strip():
            problems.append("본문이 비어 있습니다.")
        if not targets:
            problems.append("발송 대상이 없습니다. (휴대폰 번호 입력 + 수신 동의 + 수신거부 아님)")
        if len(targets) > remaining:
            problems.append(f"이번 달 {kind} 무료 잔여 {max(remaining, 0)}건보다 대상({len(targets)}명)이 많습니다.")
        if scheduled_at and scheduled_at.replace(tzinfo=None) < datetime.now(timezone(timedelta(hours=9))).replace(tzinfo=None) + timedelta(minutes=10):
            problems.append("예약 시각은 지금부터 10분 이후여야 합니다.")
        # 야간(21~08시) 제한은 데모에서는 적용하지 않는다 (서버는 적용)
        return {"type": kind, "bytes": size, "content": text, "targets": len(targets), "remaining": remaining,
                "problems": problems, "ok": not problems, "dry_run": True,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None}

    def sms_send(self, grades: list, body: str, scheduled_at=None, member_ids=None) -> dict:
        plan = self.sms_preview(grades, body, scheduled_at, member_ids)
        if not plan["ok"]:
            raise Unsupported("; ".join(plan["problems"]))
        rid = f"dryrun-{len(self.sms_logs_) + 1:04d}"
        self.sms_logs_.insert(0, {"id": len(self.sms_logs_) + 1, "ts": _iso(datetime.now(timezone.utc)),
                                  "month": TODAY.strftime("%Y-%m"), "request_id": rid, "type": plan["type"],
                                  "content": plan["content"], "target_count": plan["targets"], "error": None,
                                  "status": "scheduled" if scheduled_at else "dry_run", "scheduled_at": plan["scheduled_at"]})
        return {"request_id": rid, "count": plan["targets"], "dry_run": True, "scheduled_at": plan["scheduled_at"]}

    def sms_cancel(self, log_id: int) -> dict:
        log = next((x for x in self.sms_logs_ if x["id"] == log_id), None)
        if log is None or log["status"] != "scheduled":
            raise Unsupported("예약 상태의 문자만 취소할 수 있습니다.")
        log["status"] = "canceled"
        return dict(log)

    def sms_logs(self) -> list:
        self.sms_usage()
        return [dict(x) for x in self.sms_logs_]

    def opt_out(self, member_id: int) -> dict:
        member = next((m for m in self.members_ if m["id"] == member_id), None)
        if member:
            member["opted_out"] = True
        return {"id": member_id, "opted_out": True}
