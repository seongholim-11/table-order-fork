"""직원 호출 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 테이블은 staff_calls (처리 화면은 없어 done 은 done_at 으로 보관).

[뼈대] 시그니처와 스키마만 남겼다. 구현은 TODO 를 따라 채운다.
"""

SCHEMA = """\
CREATE TABLE IF NOT EXISTS staff_calls (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no   INTEGER NOT NULL,
    items      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    done_at    TEXT
);
"""


class CallMixin:
    def add_call(self, table_no: int, items: list[str]) -> dict:
        """호출을 저장하고 {id, ts, table_no, items, done} 을 돌려준다.

        TODO: staff_calls 에 INSERT (items 는 db.to_list), 저장한 호출을 call() 로 읽어 반환."""
        raise NotImplementedError

    def call(self, call_id: int) -> dict:
        """TODO: 한 건 조회. items 는 db.from_list, done 은 done_at 이 있으면 True."""
        raise NotImplementedError
