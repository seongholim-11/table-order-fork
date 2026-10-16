# 관리자 AI 마케팅 추천 초안

이 폴더는 사장님 화면의 **AI 추천**에 필요한 코드만 모은다. 화면 배치는 `admin/views/marketing.py`, 서버 호출은 `admin/admin_repository.py`에 두고, 여기서는 데이터를 읽기 쉬운 모양으로 정리하고 추천 카드를 계산한다.

| 파일 | 역할 |
|---|---|
| `config.py` | 한 화면의 카드 수와 빈 데이터 안내처럼 공통 설정 관리 |
| `consumer_data.py` | 고객 수, 등급, 문자 수신 가능 고객 집계 |
| `revenue_data.py` | 주문 수, 매출, 평균 주문금액, 피크 시간, 인기 메뉴 집계 |
| `menu_data.py` | 판매 중·품절·미판매 메뉴 집계 |
| `context.py` | 고객·매출·메뉴·문자 데이터를 추천 입력 하나로 조립 |
| `recommendations.py` | 근거가 있는 추천 카드 생성과 재추천 페이지 순환 |

## 다음 작업 순서

1. `DATA_SOURCE=dummy`로 관리자 앱을 켜고 `마케팅 > AI 추천`의 문구와 카드 순서를 조정한다.
2. `GET /admin/api/marketing/opportunities?round=`가 구현되면 `AdminRepository.opportunities(round)`를 추가한다.
3. API 연결 성공 시 서버 카드, 실패하거나 더미 모드이면 현재 로컬 계산을 사용한다.
4. `backend/app/services/stats.py`가 완성되기 전에는 AI 적중률처럼 없는 데이터의 카드를 건너뛴다.

성호 담당인 AI 문자 생성과 챗봇 코드는 이 폴더로 옮기지 않는다.
