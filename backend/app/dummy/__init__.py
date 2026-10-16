"""API 의 더미 응답 모음. 담당 기능별 파일로 나뉘어 있다 (예전에는 dummy.py 한 파일이었다).

  store_data 매장 정보 / content_data 화면용 콘텐츠 / menu_data 메뉴 / coupon_data 쿠폰함·룰렛 당첨
  order_data 주문·회원 원본 / stats_data 대시보드 통계 / call_data 직원 호출 / recommend_data AI 추천 기록

라우터는 예전처럼 `from app import dummy` 후 `dummy.xxx()` 로 부른다 (아래에서 각 파일의 함수를 모아 다시 내보낸다).

팀원이 엔드포인트를 하나씩 실제 DB 로 바꿀 때:
  1. 해당 라우터 함수에서 `dummy.xxx()` 호출을 store/service 호출로 바꾼다.
  2. 본인 담당 `*_data.py` 에서 그 함수와 그 파일의 ENDPOINTS 줄을 지운다 (이 __init__.py 는 고치지 않는다).
라우터에서 `dummy.` 로 시작하는 호출이 남아 있으면 아직 더미인 엔드포인트다. (`grep -rn "dummy\\." app/routers`)

쓰기(POST/PUT/DELETE)도 같은 방식으로 DB 에 저장하지 않고 "성공한 것처럼" 더미 응답을 돌려준다.
교체할 때는 라우터의 TODO 주석을 따라 store 함수를 구현하고 해당 더미 함수를 지운다.

QR 로그인(/api/auth/*, /api/members/me, /api/tables/{n}/logins)과 문자 발송(/admin/api/marketing/sms/*)은 더미가 아니다.
고객 목록(GET /admin/api/members)도 문자 발송 대상·수신거부와 같은 회원 id 를 쓰므로 DB 를 그대로 읽는다.
응답 모양은 지금 화면(user/, admin/)이 쓰는 것과 같다. 더미 쓰기는 아무것도 저장하지 않으므로 이후 조회에도 반영되지 않는다.
"""

# 파일마다 공개 함수를 모두 가져온다. 함수를 지워도 이 파일은 고칠 필요가 없다.
from app.dummy import call_data, content_data, coupon_data, menu_data, order_data, recommend_data, stats_data, store_data
from app.dummy.call_data import *  # noqa: F401,F403
from app.dummy.content_data import *  # noqa: F401,F403
from app.dummy.coupon_data import *  # noqa: F401,F403
from app.dummy.menu_data import *  # noqa: F401,F403
from app.dummy.order_data import *  # noqa: F401,F403
from app.dummy.recommend_data import *  # noqa: F401,F403
from app.dummy.stats_data import *  # noqa: F401,F403
from app.dummy.store_data import *  # noqa: F401,F403

# 더미인 엔드포인트 목록 (각 파일의 ENDPOINTS 를 합친 것). 테스트가 여기 적힌 함수가 실제로 있는지 확인한다.
DUMMY_ENDPOINTS = {
    **store_data.ENDPOINTS, **content_data.ENDPOINTS, **menu_data.ENDPOINTS, **coupon_data.ENDPOINTS,
    **order_data.ENDPOINTS, **stats_data.ENDPOINTS, **call_data.ENDPOINTS, **recommend_data.ENDPOINTS,
}
del ENDPOINTS  # 파일마다 같은 이름이라 마지막 것이 남아 헷갈리므로 지운다
