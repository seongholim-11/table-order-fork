"""쿠폰함 저장소. 룰렛에 당첨되면 쿠폰이 하나 생기고, 주문에 쓰면 사용 처리된다.

룰렛은 회원당 하루 1회(한국 시간 기준, 다른 테이블에서도 같은 날은 불가)이므로
'오늘 이 회원에게 발급된 쿠폰이 있는가'가 곧 '오늘 룰렛을 돌렸는가'이다.
"""

from datetime import datetime, timedelta, timezone

from app.stores.db import Database
from app.stores.members import now_iso

KST = timezone(timedelta(hours=9))

SCHEMA = """CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL, table_no INTEGER NOT NULL,
    kind TEXT NOT NULL, label TEXT NOT NULL, emoji TEXT NOT NULL DEFAULT '🎁', percent INTEGER, item_id TEXT,
    issued_at TEXT NOT NULL, used_at TEXT, used_order_id INTEGER)"""

COLUMNS = "id, member_id, table_no, kind, label, emoji, percent, item_id, issued_at, used_at, used_order_id"


def _today_start_utc() -> str:
    """오늘 0시(KST)를 UTC ISO 문자열로. issued_at 과 같은 형식이라 문자열 비교로 하루를 가른다."""
    midnight = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).isoformat(timespec="seconds")


class CouponStore:
    def __init__(self, db: Database):
        self.db = db
        self.db.script(SCHEMA)

    def issued_today(self, member_id: int) -> bool:
        """오늘(KST) 이 회원이 이미 룰렛에 당첨돼 쿠폰을 받았는지 (테이블과 무관)."""
        return self.db.one("SELECT 1 AS x FROM coupons WHERE member_id=? AND issued_at>=?",
                           (member_id, _today_start_utc())) is not None

    def issue(self, member_id: int, table_no: int, kind: str, label: str, emoji: str,
              percent: int | None, item_id: str | None) -> dict:
        cid = self.db.run("INSERT INTO coupons (member_id, table_no, kind, label, emoji, percent, item_id, issued_at) "
                          "VALUES (?,?,?,?,?,?,?,?)",
                          (member_id, table_no, kind, label, emoji, percent, item_id, now_iso()))
        return self.get(cid)

    def get(self, coupon_id: int) -> dict | None:
        return self.db.one(f"SELECT {COLUMNS} FROM coupons WHERE id=?", (coupon_id,))

    def for_member(self, member_id: int) -> list[dict]:
        """내 쿠폰: 안 쓴 것 먼저, 그 안에서는 최근 발급순."""
        return self.db.all(f"SELECT {COLUMNS} FROM coupons WHERE member_id=? "
                           "ORDER BY used_at IS NOT NULL, id DESC", (member_id,))

    def for_members(self, member_ids: list[int]) -> list[dict]:
        """이 태블릿에 로그인한 회원들의 쿠폰 (닉네임 포함). 안 쓴 것 먼저, 최근 발급순."""
        if not member_ids:
            return []
        marks = ",".join("?" * len(member_ids))
        return self.db.all(
            f"SELECT c.id, c.member_id, m.nickname, c.table_no, c.kind, c.label, c.emoji, c.percent, c.item_id, "
            f"c.issued_at, c.used_at, c.used_order_id FROM coupons c JOIN members m ON m.id=c.member_id "
            f"WHERE c.member_id IN ({marks}) ORDER BY c.used_at IS NOT NULL, c.id DESC", tuple(member_ids))

    def use(self, coupon_ids: list[int], member_ids: list[int], order_id: int) -> list[int]:
        """주문에 쓴 쿠폰을 사용 처리한다. 주어진 회원의 아직 안 쓴 쿠폰만 되고, 처리된 id 를 돌려준다."""
        used = []
        for cid in dict.fromkeys(coupon_ids):
            row = self.get(cid)
            if row and row["member_id"] in member_ids and row["used_at"] is None:
                self.db.run("UPDATE coupons SET used_at=?, used_order_id=? WHERE id=? AND used_at IS NULL",
                            (now_iso(), order_id, cid))
                used.append(cid)
        return used
