"""날씨 조회 서비스.

외부 날씨 API를 붙이기 전에는 호출하지 않고, AI 콘텐츠 저장소가 보관한
마지막 값을 읽기만 한다. 나중에 갱신 로직이 추가되어도 라우터 계약은 유지한다.
"""


def current_weather(store) -> dict:
    """현재 날씨를 {code, label, icon} 모양으로 반환한다."""
    return store.current_weather()
