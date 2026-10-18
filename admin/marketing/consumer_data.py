"""고객 데이터를 AI 마케팅 추천에 필요한 숫자로 정리한다."""


def summarize_consumers(members) -> dict:
    """고객 표를 등급·문자 발송 가능 인원 중심의 작은 dict로 바꾼다."""
    if members.empty:
        return {"total": 0, "grades": {}, "sendable": 0, "opted_out": 0, "pool_by_grade": {}}

    # 백엔드 문자 발송과 동일하게 전화번호·수신 동의·수신 거부를 모두 확인한다.
    # 예전 테스트 표처럼 전화번호 열이 없는 입력은 기존 호환을 위해 보유한 것으로 본다.
    has_phone = members["전화번호 보유"] if "전화번호 보유" in members else True
    sendable = members[has_phone & members["마케팅 수신 동의"] & ~members["수신거부"]]
    return {
        "total": len(members),
        "grades": dict(members["등급"].value_counts()),
        "sendable": len(sendable),
        "opted_out": int(members["수신거부"].sum()),
        "pool_by_grade": dict(sendable["등급"].value_counts()) if len(sendable) else {},
    }

