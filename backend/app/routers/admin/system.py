"""관리자: 서버 상태 점검 (DB 연결 검증)."""

from fastapi import APIRouter, Request

from app.stores.db_check import DbCheckStore

router = APIRouter()


@router.get("/system/db")
async def check_db(request: Request):
    """서버가 DB(Supabase Postgres 또는 로컬 SQLite)에 붙어 있는지와 필요한 테이블이 다 있는지 확인한다.

    DATABASE_URL 을 바꾼 뒤 '진짜 Supabase 에 붙었는지' 볼 때 쓴다. 연결 주소·비밀번호는 응답에 넣지 않는다.
    """
    return DbCheckStore(request.app.state.db).check()
