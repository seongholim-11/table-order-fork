"""QR 로그인 세션 저장소 (메모리). 정식 운영에서 여러 프로세스를 쓰면 Redis로 교체한다.

상태: waiting → scanned → logged_in, 또는 rejected(이미 이 태블릿에서 로그인한 회원), expired. 되돌리기 없음.
token  : QR에 들어가는 값. 휴대폰이 사용한다.
secret : 태블릿만 가지는 값. WebSocket/폴링 인증에 쓴다 (QR을 찍은 사람이 로그인 결과를 가로채지 못하게 분리).
"""

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LoginSession:
    token: str
    secret: str
    table_no: int
    created: float
    status: str = "waiting"
    member: dict | None = None
    access_token: str | None = None
    pkce_verifier: str | None = None  # Supabase PKCE 용. 서버만 보관한다
    blocked_member_ids: frozenset = frozenset()  # 이 태블릿에서 이미 로그인한 회원 id. 다시 로그인하지 못하게 막는다
    marketing_consent: bool = False  # 휴대폰에서 받은 광고성 문자 수신 동의 (로그인 완료 때 회원에 저장)
    claimed: bool = False  # 로그인 결과를 태블릿이 이미 받아갔는지
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class LoginSessionStore:
    def __init__(self, ttl_seconds: int = 180, clock: Callable[[], float] = time.time):
        self.ttl = ttl_seconds
        self.clock = clock
        self._by_token: dict[str, LoginSession] = {}
        self._by_secret: dict[str, LoginSession] = {}

    def create(self, table_no: int, blocked_member_ids=()) -> LoginSession:
        self._purge()
        s = LoginSession(secrets.token_urlsafe(16), secrets.token_urlsafe(24), table_no, self.clock(),
                         blocked_member_ids=frozenset(blocked_member_ids))
        self._by_token[s.token] = s
        self._by_secret[s.secret] = s
        return s

    def discard(self, secret: str) -> bool:
        """QR 재생성 시 이전 세션을 정리한다. 로그인 완료된 세션은 결과를 아직 못 받았을 수 있어 남겨 둔다."""
        s = self._by_secret.get(secret)
        if not s or s.status == "logged_in":
            return False
        self._by_secret.pop(secret, None)
        self._by_token.pop(s.token, None)
        self._publish(s, {"event": "expired"})
        return True

    def by_token(self, token: str) -> LoginSession | None:
        return self._by_token.get(token)

    def by_secret(self, secret: str) -> LoginSession | None:
        return self._by_secret.get(secret)

    def status(self, s: LoginSession) -> str:
        if s.status not in ("logged_in", "rejected") and self.clock() - s.created > self.ttl:
            s.status = "expired"
        return s.status

    def remaining(self, s: LoginSession) -> float:
        return max(0.0, self.ttl - (self.clock() - s.created))

    def mark_scanned(self, s: LoginSession) -> bool:
        if self.status(s) != "waiting":
            return self.status(s) == "scanned"  # 이미 스캔된 QR 재방문(새로고침)은 허용
        s.status = "scanned"
        self._publish(s, {"event": "scanned"})
        return True

    def complete(self, s: LoginSession, member: dict, access_token: str) -> bool:
        """스캔된 세션만 한 번 승인할 수 있다."""
        if self.status(s) != "scanned":
            return False
        s.status, s.member, s.access_token = "logged_in", member, access_token
        self._publish(s, {"event": "logged_in"})
        return True

    def reject(self, s: LoginSession) -> bool:
        """이미 이 태블릿에서 로그인한 회원이라 거절한다. 스캔된 세션만."""
        if self.status(s) != "scanned":
            return False
        s.status = "rejected"
        self._publish(s, {"event": "status", "status": "rejected"})
        return True

    def claim(self, s: LoginSession) -> dict | None:
        """로그인 결과(JWT 포함)를 태블릿에 한 번만 넘긴다."""
        if s.status != "logged_in" or s.claimed:
            return None
        s.claimed = True
        return {"event": "logged_in", "member": s.member, "access_token": s.access_token}

    def subscribe(self, s: LoginSession) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        s.subscribers.append(q)
        return q

    def unsubscribe(self, s: LoginSession, q: asyncio.Queue) -> None:
        if q in s.subscribers:
            s.subscribers.remove(q)

    def _publish(self, s: LoginSession, event: dict) -> None:
        for q in list(s.subscribers):
            q.put_nowait(event)

    def _purge(self) -> None:
        """만료 후 10분이 지난 세션을 정리한다."""
        cutoff = self.clock() - self.ttl - 600
        for token in [t for t, s in self._by_token.items() if s.created < cutoff]:
            s = self._by_token.pop(token)
            self._by_secret.pop(s.secret, None)
