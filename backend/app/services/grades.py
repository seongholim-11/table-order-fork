"""고객 등급(신규·재방문·단골·휴면)과 연령대 계산. 기준값은 설정/요청으로 바꿀 수 있다 (정책 미확정)."""

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
GRADES = ["신규", "재방문", "단골", "휴면"]
AGE_GROUPS = ["20대 미만", "20대", "30대", "40대", "50대 이상"]


def to_kst_date(iso: str | None) -> date | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso).astimezone(KST).date()


def grade_of(member: dict, today: date, repeat: int = 2, regular: int = 5, dormant: int = 30) -> str:
    last = to_kst_date(member.get("last_visit_at"))
    if last and (today - last).days >= dormant:
        return "휴면"
    visits = member.get("visit_count") or 0
    if visits >= regular:
        return "단골"
    if visits >= repeat:
        return "재방문"
    return "신규"


def age_group(birth_year: int | None, today: date) -> str | None:
    if not birth_year:
        return None
    age = today.year - birth_year
    return "20대 미만" if age < 20 else "20대" if age < 30 else "30대" if age < 40 else "40대" if age < 50 else "50대 이상"


def gender_label(g: str | None) -> str | None:
    return {"male": "남", "female": "여", "남": "남", "여": "여"}.get(g or "")


def grade_counts(members: list[dict], today: date, **rule) -> dict:
    """기존 등급 판정 함수를 재사용해 인원을 집계한다. DB에 등급을 저장하지 않는다."""
    counts = {grade: 0 for grade in GRADES}
    for member in members:
        counts[grade_of(member, today, **rule)] += 1
    return {**counts, "dormant_count": counts["휴면"]}
