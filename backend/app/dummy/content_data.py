"""화면용 콘텐츠(카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙) 더미. (카테고리 서준 / 룰렛·직원호출 석원 / AI 질문·날씨·추천 규칙 재현이 함께 쓴다)"""

from app.dummy._common import _json

# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "GET /api/content, /api/content/{name}": "content / content_item",
    "PUT /admin/api/content/{name}": "content_saved",
}


def content() -> dict:
    """카테고리·룰렛·직원호출 항목·AI 질문·날씨·추천 규칙. 모양은 seed/content.json 과 같다."""
    return _json("content.json")


def content_item(name: str):
    return content().get(name)


def content_saved(data):
    return data
