"""쿠폰함 저장소. 룰렛에 당첨되면 쿠폰이 하나 생기고, 주문에 쓰면 사용 처리된다.

룰렛은 회원당 하루 1회(한국 시간 기준, 다른 테이블에서도 같은 날은 불가)이므로
'오늘 이 회원에게 발급된 쿠폰이 있는가'가 곧 '오늘 룰렛을 돌렸는가'이다.
[뼈대] issued_today 는 QR 로그인(routers/auth.py)이 쓰므로 남겨 두었고, 나머지는 시그니처만 남겼다.
"""

from datetime import datetime, timezone

from app.services.grades import KST
from app.stores.db import Database


SCHEMA = """\
CREATE TABLE IF NOT EXISTS coupons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id     INTEGER NOT NULL,
    table_no      INTEGER NOT NULL,
    table_login_id INTEGER,
    prize_id     INTEGER,
    kind          TEXT NOT NULL,
    label         TEXT NOT NULL,
    emoji         TEXT NOT NULL DEFAULT '🎁',
    percent       INTEGER,
    menu_id       TEXT,
    issued_at     TEXT NOT NULL,
    expires_at    TEXT,
    used_at       TEXT,
    used_order_id INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS coupons_one_per_table_login
    ON coupons (table_login_id) WHERE table_login_id IS NOT NULL;
"""

COLUMNS = "id, member_id, table_no, kind, label, emoji, percent, menu_id AS item_id, issued_at, used_at, used_order_id"


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
              percent: int | None, item_id: str | None,
              prize_id: int | None = None, table_login_id: int | None = None) -> dict:
        """룰렛 당첨 쿠폰을 발급하고 get() 모양으로 돌려준다.

        prize_id: 당첨된 룰렛 칸(roulette_prizes.id). 모르면 None (시연에는 없어도 동작).
        table_login_id: 이 룰렛을 돌린 로그인 기록(table_logins.id). tablet_logins.set_prize 가 돌려준 값을 넣는다.
                        coupons.table_login_id 가 UNIQUE 라서 '룰렛 1번 = 쿠폰 1장'을 DB 가 보장해 준다.
        """

        issued_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        coupon_id = self.db.run(
            "INSERT INTO coupons (member_id, table_no, table_login_id, prize_id, kind, label, emoji, "
            "percent, menu_id, issued_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (member_id, table_no, table_login_id, prize_id, kind, label, emoji, percent, item_id, issued_at),
        )
        return self.get(coupon_id)

    def get(self, coupon_id: int) -> dict | None:
        return self.db.one(f"SELECT {COLUMNS} FROM coupons WHERE id=?", (coupon_id,))

    def for_member(self, member_id: int) -> list[dict]:
        """내 쿠폰: 안 쓴 것 먼저, 그 안에서는 최근 발급순.
        """

        return self.db.all(
            f"SELECT {COLUMNS} FROM coupons WHERE member_id=? ORDER BY used_at IS NOT NULL, id DESC",
            (member_id,),
        )

    def for_members(self, member_ids: list[int]) -> list[dict]:
        """이 태블릿에 로그인한 회원들의 쿠폰 (닉네임 포함). 안 쓴 것 먼저, 최근 발급순.
        """

        member_ids = list(dict.fromkeys(member_ids))
        if not member_ids:
            return []
        marks = ",".join("?" for _ in member_ids)
        return self.db.all(
            "SELECT c.id, c.member_id, m.nickname, c.table_no, c.kind, c.label, c.emoji, c.percent, "
            "c.menu_id AS item_id, c.issued_at, c.used_at, c.used_order_id "
            f"FROM coupons c JOIN members m ON m.id=c.member_id WHERE c.member_id IN ({marks}) "
            "ORDER BY c.used_at IS NOT NULL, c.id DESC",
            tuple(member_ids),
        )

    def use(self, coupon_ids: list[int], member_ids: list[int], order_id: int) -> list[int]:
        """주문에 쓴 쿠폰을 사용 처리하고, 처리된 id 를 돌려준다.
        """

        if not coupon_ids or not member_ids:
            return []
        allowed = set(member_ids)
        used: list[int] = []
        used_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for coupon_id in dict.fromkeys(coupon_ids):
            row = self.db.one("SELECT member_id FROM coupons WHERE id=? AND used_at IS NULL", (coupon_id,))
            if not row or row["member_id"] not in allowed:
                continue
            self.db.run(
                "UPDATE coupons SET used_at=?, used_order_id=? WHERE id=? AND used_at IS NULL",
                (used_at, order_id, coupon_id),
            )
            used.append(coupon_id)
        return used
