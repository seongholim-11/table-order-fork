"""솔라피(Solapi) 문자 발송.

SMS_DRY_RUN=true(기본)이면 외부를 호출하지 않고 로그만 남긴다.
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from datetime import time as dtime

import httpx

from app.core.settings import Settings
from app.services.grades import KST, grade_of
from app.stores.members import MemberStore
from app.stores.grade_rules import GradeRuleStore
from app.stores.sms_logs import SmsLogStore

SMS_LIMIT_BYTES = 90
MIN_LEAD = timedelta(minutes=10)  # 예약은 지금부터 최소 10분 뒤
NIGHT_START, NIGHT_END = dtime(21, 0), dtime(8, 0)  # 광고성 문자 야간 발송 제한
SOLAPI_BASE = "https://api.solapi.com"
SOLAPI_CHUNK = 1000  # 솔라피 send-many 1회 호출 상한은 10,000건이지만 여유를 둔다


def solapi_auth(api_key: str, api_secret: str, date: str, salt: str) -> str:
    """솔라피 HMAC-SHA256 인증 헤더 (공식 SDK authenticator 와 같은 규칙)."""
    sig = hmac.new(api_secret.encode(), (date + salt).encode(), hashlib.sha256).hexdigest()
    return f"HMAC-SHA256 ApiKey={api_key}, Date={date}, salt={salt}, signature={sig}"


class SmsRejected(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def msg_bytes(text: str) -> int:
    return sum(1 if ord(ch) < 128 else 2 for ch in text)


def msg_type(text: str) -> str:
    return "SMS" if msg_bytes(text) <= SMS_LIMIT_BYTES else "LMS"


def is_night(now: dtime) -> bool:
    return now >= NIGHT_START or now < NIGHT_END


class SmsService:
    def __init__(self, settings: Settings, members: MemberStore, logs: SmsLogStore, clock=None, http=None):
        self.s, self.members, self.logs = settings, members, logs
        self.clock = clock or (lambda: datetime.now(KST))
        self.http = http  # 테스트에서 가짜 httpx.Client 주입

    def _configured(self) -> bool:
        s = self.s
        return bool(s.solapi_api_key and s.solapi_api_secret and s.solapi_sender_number and s.sms_opt_out_number)

    def build(self, body: str) -> str:
        number = self.s.sms_opt_out_number or "080-000-0000"
        return f"(광고){self.s.store_name}\n{body.strip()}\n무료수신거부 {number}"

    def targets(self, grades: list[str], member_ids: list[int] | None = None) -> list[dict]:
        today = self.clock().date()
        rule = self.grade_rule()
        return [m for m in self.members.all()
                if m["phone"] and m["marketing_consent"] and not m["opted_out"]
                and grade_of(m, today, **rule) in grades
                and (member_ids is None or m["id"] in member_ids)]

    def grade_rule(self) -> dict:
        """문자 미리보기·발송도 고객 화면과 같은 저장 기준을 매번 읽는다."""
        return GradeRuleStore(self.members.db).resolve(self.s)

    def usage(self, month: str | None = None) -> dict:
        month = month or self.clock().strftime("%Y-%m")
        used = self.logs.usage(month)
        return {"month": month, "used": used,
                "limit": {"SMS": self.s.sms_monthly_limit, "LMS": self.s.lms_monthly_limit}}

    def balance(self) -> dict:
        """솔라피에 충전된 잔액(원)과 포인트를 조회한다. 키가 없거나 호출이 실패해도 화면이 깨지지 않게 available=False 로 돌려준다."""
        s = self.s
        if not (s.solapi_api_key and s.solapi_api_secret):
            return {"available": False, "reason": "솔라피 API 키가 설정되지 않았습니다."}
        date = datetime.now(timezone.utc).isoformat(timespec="seconds")
        headers = {"Authorization": solapi_auth(s.solapi_api_key, s.solapi_api_secret, date, uuid.uuid4().hex)}
        try:
            client = self.http or httpx.Client(timeout=10)
            r = client.get(SOLAPI_BASE + "/cash/v1/balance", headers=headers)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            data = r.json()
            # 응답의 balance(잔액)·point(포인트)는 원 단위 금액이다.
            return {"available": True, "balance": data.get("balance", 0), "point": data.get("point", 0)}
        except Exception as e:  # 네트워크·인증 오류 모두 화면에는 이유만 전달
            return {"available": False, "reason": f"잔액 조회 실패: {e}"[:200]}

    def preview(self, grades: list[str], body: str, scheduled_at: datetime | None = None,
                member_ids: list[int] | None = None) -> dict:
        text = self.build(body)
        kind = msg_type(text)
        when = self._kst(scheduled_at) if scheduled_at else None
        usage = self.usage(when.strftime("%Y-%m") if when else None)
        remaining = usage["limit"][kind] - usage["used"][kind]
        targets = self.targets(grades, member_ids)
        problems = []
        if not body.strip():
            problems.append("본문이 비어 있습니다.")
        if not targets:
            problems.append("발송 대상이 없습니다. (휴대폰 번호 입력 + 수신 동의 + 수신거부 아님)")
        if when:
            if when < self.clock() + MIN_LEAD:
                problems.append("예약 시각은 지금부터 10분 이후여야 합니다.")
        if is_night((when or self.clock()).timetz().replace(tzinfo=None)):
            problems.append("야간(21시~08시)에는 광고성 문자를 보낼 수 없습니다.")
        if len(targets) > remaining:
            problems.append(f"이번 달 {kind} 무료 잔여 {max(remaining, 0)}건보다 대상({len(targets)}명)이 많습니다.")
        if not self.s.sms_dry_run and not self._configured():
            problems.append("솔라피 설정(API 키·시크릿·발신번호·수신거부 번호)이 비어 있습니다.")
        return {"type": kind, "bytes": msg_bytes(text), "content": text, "targets": len(targets),
                "remaining": remaining, "problems": problems, "ok": not problems, "dry_run": self.s.sms_dry_run,
                "scheduled_at": when.isoformat() if when else None}

    def _kst(self, when: datetime) -> datetime:
        return (when.replace(tzinfo=KST) if when.tzinfo is None else when).astimezone(KST)

    def send(self, grades: list[str], body: str, scheduled_at: datetime | None = None,
             member_ids: list[int] | None = None) -> dict:
        plan = self.preview(grades, body, scheduled_at, member_ids)
        if not plan["ok"]:
            raise SmsRejected(plan["problems"])
        targets = self.targets(grades, member_ids)
        when = self._kst(scheduled_at) if scheduled_at else None
        month = (when or self.clock()).strftime("%Y-%m")
        kind, text, sched = plan["type"], plan["content"], when.isoformat() if when else None
        if self.s.sms_dry_run:
            rid = f"dryrun-{uuid.uuid4().hex[:12]}"
            self.logs.add(month, kind, text, len(targets), "scheduled" if when else "dry_run", rid, scheduled_at=sched)
            return {"request_id": rid, "count": len(targets), "dry_run": True, "scheduled_at": sched}
        sent, ids = 0, []
        for i in range(0, len(targets), SOLAPI_CHUNK):
            chunk = targets[i:i + SOLAPI_CHUNK]
            try:
                rid = self._call_solapi(kind, text, [m["phone"] for m in chunk], when)
            except Exception as e:  # 한 묶음이 실패해도 앞서 보낸 것은 기록을 남긴다
                self.logs.add(month, kind, text, len(chunk), "failed", error=str(e)[:300], scheduled_at=sched)
                raise SmsRejected([f"솔라피 발송 실패: {e}"]) from e
            self.logs.add(month, kind, text, len(chunk), "scheduled" if when else "sent", rid, scheduled_at=sched)
            sent += len(chunk)
            ids.append(rid)
        return {"request_id": ",".join(ids), "count": sent, "dry_run": False, "scheduled_at": sched}

    def send_test(self, phone: str, body: str) -> dict:
        """관리자 테스트용: 회원·동의 조건 없이 입력한 번호 1건으로 즉시 발송한다. 월 한도·야간 제한은 그대로 적용."""
        digits = phone.replace("-", "").strip()
        if not (digits.isdigit() and 10 <= len(digits) <= 11 and digits.startswith("01")):
            raise SmsRejected(["수신번호 형식이 올바르지 않습니다. (예: 010-1234-5678)"])
        if not body.strip():
            raise SmsRejected(["본문이 비어 있습니다."])
        text = f"[테스트] {body.strip()}"
        kind, now = msg_type(text), self.clock()
        month = now.strftime("%Y-%m")
        usage = self.usage(month)
        problems = []
        if is_night(now.timetz().replace(tzinfo=None)):
            problems.append("야간(21시~08시)에는 문자를 보낼 수 없습니다.")
        if usage["limit"][kind] - usage["used"][kind] < 1:
            problems.append(f"이번 달 {kind} 무료 잔여가 없습니다.")
        if not self.s.sms_dry_run and not (
                self.s.solapi_api_key and self.s.solapi_api_secret and self.s.solapi_sender_number):
            problems.append("솔라피 설정(API 키·시크릿·발신번호)이 비어 있습니다.")
        if problems:
            raise SmsRejected(problems)
        if self.s.sms_dry_run:
            rid = f"dryrun-{uuid.uuid4().hex[:12]}"
            self.logs.add(month, kind, text, 1, "dry_run", rid)
            return {"ok": True, "dry_run": True, "type": kind, "request_id": rid, "to": digits}
        try:
            rid = self._call_solapi(kind, text, [digits])
        except Exception as e:
            self.logs.add(month, kind, text, 1, "failed", error=str(e)[:300])
            raise SmsRejected([f"솔라피 발송 실패: {e}"]) from e
        self.logs.add(month, kind, text, 1, "sent", rid)
        return {"ok": True, "dry_run": False, "type": kind, "request_id": rid, "to": digits}

    def cancel(self, log_id: int) -> dict | None:
        """예약 문자를 취소한다. 없는 기록이면 None, 취소할 수 없으면 SmsRejected."""
        log = self.logs.get(log_id)
        if not log:
            return None
        if log["status"] != "scheduled":
            raise SmsRejected(["예약 상태의 문자만 취소할 수 있습니다."])
        if datetime.fromisoformat(log["scheduled_at"]) <= self.clock():
            raise SmsRejected(["이미 예약 시각이 지나 취소할 수 없습니다."])
        rid = log["request_id"] or ""
        if not rid.startswith("dryrun-"):
            try:
                self._cancel_solapi(rid)
            except Exception as e:
                raise SmsRejected([f"솔라피 예약 취소 실패: {e}"]) from e
        self.logs.set_status(log_id, "canceled")
        return {**log, "status": "canceled"}

    def _cancel_solapi(self, group_id: str) -> None:
        s = self.s
        date = datetime.now(timezone.utc).isoformat(timespec="seconds")
        headers = {"Authorization": solapi_auth(s.solapi_api_key, s.solapi_api_secret, date, uuid.uuid4().hex)}
        client = self.http or httpx.Client(timeout=10)
        r = client.delete(f"{SOLAPI_BASE}/messages/v4/groups/{group_id}/schedule", headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")

    def _call_solapi(self, kind: str, text: str, phones: list[str], scheduled_at: datetime | None = None) -> str:
        """send-many/detail 로 한 묶음을 보내고 그룹 ID 를 돌려준다."""
        s = self.s
        date = datetime.now(timezone.utc).isoformat(timespec="seconds")
        headers = {"Authorization": solapi_auth(s.solapi_api_key, s.solapi_api_secret, date, uuid.uuid4().hex),
                   "Content-Type": "application/json"}
        sender = s.solapi_sender_number.replace("-", "")
        messages = []
        for p in phones:
            m = {"to": p.replace("-", ""), "from": sender, "text": text, "type": kind}
            if kind == "LMS":
                m["subject"] = f"(광고){s.store_name}"[:40]
            messages.append(m)
        client = self.http or httpx.Client(timeout=10)
        payload = {"messages": messages}
        if scheduled_at:
            payload["scheduledDate"] = scheduled_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        r = client.post(SOLAPI_BASE + "/messages/v4/send-many/detail", json=payload, headers=headers)
        if r.status_code >= 400:
            try:
                err = r.json()
                raise RuntimeError(f"{err.get('errorCode', r.status_code)} {err.get('errorMessage', '')}".strip())
            except ValueError:
                raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]}") from None
        data = r.json()
        count = (data.get("groupInfo") or {}).get("count") or {}
        if phones and count.get("total") and count.get("total") == count.get("registeredFailed"):
            raise RuntimeError(f"모든 메시지 접수 실패: {str(data.get('failedMessageList'))[:200]}")
        return (data.get("groupInfo") or {}).get("groupId") or data.get("groupId", "")
