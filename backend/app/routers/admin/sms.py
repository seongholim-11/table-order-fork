"""관리자: 마케팅 문자 발송."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.grades import GRADES
from app.services.sms import SmsRejected, SmsService

router = APIRouter()


class SmsIn(BaseModel):
    grades: list[str] = Field(min_length=1)
    member_ids: list[int] | None = None  # 주면 등급 대상 중 이 회원들로만 좁힌다(대상 목록 수동 수정)
    body: str
    scheduled_at: datetime | None = None  # 예약 발송 시각 (시간대 없으면 KST)


class SmsTestIn(BaseModel):
    phone: str
    body: str = Field(min_length=1)


def _sms(request: Request) -> SmsService:
    return request.app.state.sms


def _check_grades(grades: list[str]) -> None:
    if any(g not in GRADES for g in grades):
        raise HTTPException(422, f"등급은 {GRADES} 중에서 고르세요.")


@router.get("/marketing/sms/usage")
async def sms_usage(request: Request):
    return _sms(request).usage()


@router.get("/marketing/sms/balance")
def sms_balance(request: Request):
    """솔라피 충전 잔액·포인트. 외부 호출이 있어 동기 함수로 둔다."""
    return _sms(request).balance()


@router.post("/marketing/sms/preview")
async def sms_preview(body: SmsIn, request: Request):
    _check_grades(body.grades)
    return _sms(request).preview(body.grades, body.body, body.scheduled_at, body.member_ids)


@router.post("/marketing/sms/send")
def sms_send(body: SmsIn, request: Request):
    _check_grades(body.grades)
    try:
        return _sms(request).send(body.grades, body.body, body.scheduled_at, body.member_ids)
    except SmsRejected as e:
        raise HTTPException(409, {"problems": e.problems})


@router.post("/sms/test")
def sms_test(body: SmsTestIn, request: Request):
    """수신번호 1건으로 바로 문자를 보내 본다 (관리자 인증 필수, 회원·동의 조건 없음)."""
    try:
        return _sms(request).send_test(body.phone, body.body)
    except SmsRejected as e:
        raise HTTPException(409, {"ok": False, "problems": e.problems})


@router.post("/marketing/sms/logs/{log_id}/cancel")
def sms_cancel(log_id: int, request: Request):
    try:
        done = _sms(request).cancel(log_id)
    except SmsRejected as e:
        raise HTTPException(409, {"problems": e.problems})
    if done is None:
        raise HTTPException(404, "없는 발송 기록입니다.")
    return done


@router.get("/marketing/sms/logs")
async def sms_logs(request: Request):
    return request.app.state.sms_logs.logs()


@router.post("/marketing/sms/candidates")
def sms_candidates(request: Request):
    """AI 문자 후보 여러 개(키워드·수신 등급·문구·출처)를 만든다. 외부 호출이 있어 동기 함수로 둔다."""
    return request.app.state.sms_candidates.candidates()
