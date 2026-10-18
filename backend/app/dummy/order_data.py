"""주문 더미 응답 모음.

주문 저장·관리자 주문 이력은 실제 DB로 교체되어 더 이상 이 파일의 더미를 사용하지 않는다.
"""

ENDPOINTS = {}


# 통계 테스트가 실제 DB 사용 여부를 확인할 때 monkeypatch하는 호환용 헬퍼다.
# 라우터에서 호출하지 않으므로 더미 엔드포인트 목록에는 포함하지 않는다.
def members(rule=None) -> list[dict]:
    from app.dummy._common import _ago

    def make(i, nickname, gender, birth_year, visit_count, last_visit_at):
        return {"id": i, "kakao_id": f"dummy-{i}", "nickname": nickname, "phone": "010-0000-0000",
                "gender": gender, "birthday": None, "birth_year": birth_year,
                "marketing_consent": True, "opted_out": False, "visit_count": visit_count,
                "last_visit_at": last_visit_at, "created_at": _ago(days=90)}
    return [make(1, "민지", "female", 1998, 1, _ago(hours=1)), make(2, "준호", "male", 1990, 3, _ago(days=2))]


def orders() -> list[dict]:
    return []
