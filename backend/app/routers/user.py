"""손님 API: 회원 정보와 이 태블릿의 로그인 기록. (담당: 성호. 다른 사람은 고치지 않는다)

주문·쿠폰·룰렛·메뉴·직원 호출·AI 추천은 기능별 파일(orders.py, coupons.py, roulette.py, menus.py, staff_calls.py, ai.py)로 나뉘었다.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.dependencies import current_member

router = APIRouter(prefix="/api", tags=["사용자"])


def _me(m: dict) -> dict:
    return {"id": m["id"], "nickname": m["nickname"], "phone": m["phone"], "birth_year": m["birth_year"],
            "gender": m["gender"], "marketing_consent": bool(m["marketing_consent"]),
            "opted_out": bool(m["opted_out"]), "visit_count": m["visit_count"]}


@router.get("/members/me")
async def get_me(member: dict = Depends(current_member)):
    return _me(member)


@router.post("/members/me/opt-out")
async def opt_out(request: Request, member: dict = Depends(current_member)):
    return _me(request.app.state.members.opt_out(member["id"]))


def tablet_rows(request: Request, table_no: int, member: dict) -> list[dict]:
    """이 태블릿에 로그인한 회원만 그 태블릿의 기록을 볼 수 있다. (쿠폰함·룰렛 라우터도 가져다 쓴다)"""
    rows = request.app.state.tablet_logins.list(table_no)
    if all(r["id"] != member["id"] for r in rows):
        raise HTTPException(403, "이 태블릿에서 로그인한 회원이 아닙니다.")
    return rows


@router.get("/tables/{table_no}/logins")
async def tablet_logins(table_no: int, request: Request, member: dict = Depends(current_member)):
    """새로고침 후 '이 태블릿에서 로그인한 회원'(룰렛 사용 여부 포함)을 되살리기 위한 기록."""
    return tablet_rows(request, table_no, member)
