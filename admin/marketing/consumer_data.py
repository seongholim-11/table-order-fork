"""고객 데이터를 AI 마케팅 추천에 필요한 숫자로 정리한다."""


def summarize_consumers(members) -> dict:
    """고객 표를 등급·문자 발송 가능 인원 중심의 작은 dict로 바꾼다."""
    if members.empty:
        return {"total": 0, "grades": {}, "sendable": 0, "opted_out": 0, "pool_by_grade": {}}

    # 수신 동의와 수신 거부를 함께 확인해야 실제로 문자를 보낼 수 있는 고객만 남는다.
    sendable = members[members["마케팅 수신 동의"] & ~members["수신거부"]]
    return {
        "total": len(members),
        "grades": dict(members["등급"].value_counts()),
        "sendable": len(sendable),
        "opted_out": int(members["수신거부"].sum()),
        "pool_by_grade": dict(sendable["등급"].value_counts()) if len(sendable) else {},
    }

