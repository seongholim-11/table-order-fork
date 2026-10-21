"""관리자: 고객 목록·등급·수신거부."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services.grades import KST, age_group, gender_label, grade_counts, grade_of
from app.stores.grade_rules import GradeRule, GradeRuleStore

router = APIRouter()


@router.get("/members")
def list_members(request: Request, settings: Settings = Depends(get_settings),
                       repeat: int | None = Query(default=None, ge=2), regular: int | None = Query(default=None, ge=3),
                       dormant: int | None = Query(default=None, ge=1)):
    """고객 목록과 등급. 등급 기준은 쿼리로 미리 바꿔 볼 수 있다 (저장되지는 않음)."""
    rule, today = grade_rule(settings, repeat, regular, dormant, db=request.app.state.db), datetime.now(KST).date()
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    return {"rule": rule, "members": [
        {"id": m["id"], "nickname": m["nickname"], "gender": gender_label(m["gender"]),
         "age_group": age_group(m["birth_year"], today), "birthday": m.get("birthday"),
         "visit_count": m["visit_count"],
         "last_visit_at": m["last_visit_at"], "marketing_consent": bool(m["marketing_consent"]),
         "opted_out": bool(m["opted_out"]), "has_phone": bool(m["phone"]), "grade": grade_of(m, today, **rule)}
        for m in request.app.state.members.all()]}


@router.post("/members/{member_id}/opt-out")
def member_opt_out(member_id: int, request: Request):
    if not request.app.state.members.opt_out(member_id):
        raise HTTPException(404, "없는 회원입니다.")
    return {"ok": True}


@router.get("/customers/grades")
def customer_grades(request: Request, settings: Settings = Depends(get_settings),
                          repeat: int | None = Query(default=None, ge=2),
                          regular: int | None = Query(default=None, ge=3),
                          dormant: int | None = Query(default=None, ge=1)):
    """회원의 방문 기록을 읽어 요청한 기준으로 등급별 인원을 반환한다."""
    # 쿼리는 이번 조회에만 적용하고, 없는 값은 DB 저장 기준·서버 설정 순서로 읽는다.
    rule = grade_rule(settings, repeat, regular, dormant, db=request.app.state.db)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    return grade_counts(request.app.state.members.all(), datetime.now(KST).date(), **rule)


@router.get("/customers/grades/rules")
def customer_grade_rules(request: Request, settings: Settings = Depends(get_settings)):
    """화면의 초기값·기본값 복원에 쓰는 현재 서버 등급 기준을 반환한다."""
    return grade_rule(settings, db=request.app.state.db)


@router.put("/customers/grades/rules")
def save_customer_grade_rules(rule: GradeRule, request: Request):
    """검증된 기준만 영구 저장한다. 기존 GET과 같은 세 필드를 반환한다."""
    return GradeRuleStore(request.app.state.db).save(rule.model_dump())


# 새 고객 경로에서도 기존 함수를 그대로 사용해 목록·수신거부 응답 계약을 유지한다.
router.add_api_route("/customers", list_members, methods=["GET"])
router.add_api_route("/customers/{member_id}/opt-out", member_opt_out, methods=["POST"])


@router.get("/marketing/live-activity")
def live_activity(request: Request) -> dict:
    """새 로그인·주문이 있는지 화면이 주기적으로(폴링) 확인하는 가벼운 조회."""
    from app.stores.customer_notes import CustomerNotesStore

    return CustomerNotesStore(request.app.state.db).activity()


@router.get("/marketing/regular-preferences")
def regular_preferences(request: Request, settings: Settings = Depends(get_settings)):
    """오늘 주문한 단골·주간 반복 방문·생일·첫 방문 기념일 고객의 응대 제안을 조회한다."""
    from app.services.customer_notes import regular_notes
    from app.stores.customer_notes import CustomerNotesStore

    # 기존 고객 목록 응답은 유지하고 마케팅 화면에서만 선호도 조회를 사용한다.
    store = CustomerNotesStore(request.app.state.db)
    rule = grade_rule(settings, db=request.app.state.db)
    today = datetime.now(KST).date()
    # 날씨는 외부 호출로 지어내지 않고, 기존 서비스가 오늘 DB에 저장한 값이 있을 때만 사용한다.
    saved_weather = request.app.state.external.store.get(today.isoformat()) or {}
    notes = regular_notes(request.app.state.members.all(), store.orders(1),
                          store.lines(1), store.menus(), today, dormant_days=rule["dormant"],
                          repeat_visits=rule["repeat"], regular_visits=rule["regular"],
                          weather_text=saved_weather.get("weather_text", ""), visits=store.visits(1))
    # 사장님이 이미 '확인'한 제안인지 카드마다 표시해 화면이 미확인/확인 영역으로 나눌 수 있게 한다.
    checked = store.checked_tips()
    for note in notes:
        note["checked"] = (note.get("member_id"), note.get("current_order_id")) in checked
    return {"preferences": notes}


class TipCheck(BaseModel):
    """응대 제안 카드 하나(손님+주문)와 확인 여부."""
    member_id: int
    order_id: int
    checked: bool = True


@router.put("/marketing/tip-checks")
def set_tip_check(body: TipCheck, request: Request) -> dict:
    """응대 제안 카드를 확인 처리하거나(checked=true) 미확인으로 되돌린다(false)."""
    from app.stores.customer_notes import CustomerNotesStore

    CustomerNotesStore(request.app.state.db).set_tip_checked(body.member_id, body.order_id, body.checked)
    return {"member_id": body.member_id, "order_id": body.order_id, "checked": body.checked}
