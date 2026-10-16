"""화면용 콘텐츠(카테고리·룰렛·질문·추천 규칙 등) 저장소. 모양은 user/*_data.py 더미와 같다. [뼈대] 시그니처와 스키마만 남겼다."""

NAMES = ("categories", "roulette_prizes", "staff_calls", "quiz_questions", "weather", "rules")
SCHEMA = "CREATE TABLE IF NOT EXISTS content (name TEXT PRIMARY KEY, data TEXT NOT NULL)"


class ContentStore:
    def __init__(self, db):
        self.db = db
        db.script(SCHEMA)
        # TODO: NAMES 중 아직 없는 항목만 seed/content.json 의 값으로 채운다 (관리자가 고친 것은 덮어쓰지 않는다).

    def get(self, name: str):
        """TODO: content 테이블의 JSON 을 읽어 돌려준다. 없으면 None."""
        raise NotImplementedError

    def all(self) -> dict:
        """TODO: NAMES 전체를 {이름: 값} 으로."""
        raise NotImplementedError

    def set(self, name: str, data) -> None:
        """TODO: JSON 으로 저장 (있으면 교체)."""
        raise NotImplementedError
