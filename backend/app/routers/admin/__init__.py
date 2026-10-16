"""관리자 페이지용 API. 모든 경로에 관리자 인증이 필요하다.

기능별 파일로 나뉘어 있다. 새 관리자 API 는 해당 파일에 `router` 로 추가하고, 새 파일을 만들면 아래에 등록한다.
  menus.py 메뉴·카테고리 / orders.py 주문·직원 호출 / members.py 고객·등급 / stats.py 대시보드 통계
  sms.py 마케팅 문자 / content.py 콘텐츠(룰렛·직원 호출 항목 등) 교체 / system.py 서버·DB 연결 점검
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_admin
from app.routers.admin import content, members, menus, orders, sms, stats, system

router = APIRouter(prefix="/admin/api", tags=["관리자"], dependencies=[Depends(require_admin)])
for _module in (menus, orders, members, stats, sms, content, system):
    router.include_router(_module.router)
