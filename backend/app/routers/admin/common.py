"""관리자 라우터들이 같이 쓰는 도우미."""

from app.core.settings import Settings
from app.stores.grade_rules import GradeRuleStore


def grade_rule(s: Settings, repeat=None, regular=None, dormant=None, *, db=None) -> dict:
    """기존 호출 모양을 유지하면서 조회 미리보기 > DB > 환경 설정 순서로 읽는다."""
    base = GradeRuleStore(db).resolve(s) if db is not None else {
        "repeat": s.grade_repeat_visits, "regular": s.grade_regular_visits, "dormant": s.grade_dormant_days}
    return {key: value if value is not None else base[key]
            for key, value in (("repeat", repeat), ("regular", regular), ("dormant", dormant))}
