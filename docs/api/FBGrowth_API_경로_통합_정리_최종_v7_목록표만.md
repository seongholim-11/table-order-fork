# F&BGrowth API 경로 정리 (v7, 목록표)

> v6의 "서버 구현" 열을 2026-10-18 코드 기준으로 다시 확인해 갱신한 문서입니다. v6는 그대로 두었습니다.
> 같은 날 **QR 로그인·문자 발송을 뺀 나머지 구현 코드를 뼈대만 남기고 되돌렸고**, 구현 구분 열과 아래 집계를 그 코드 상태에 맞췄습니다.
>
> **구현 현황 표기**
> - **구현**: 실제 DB(또는 외부 서비스)에 저장·조회함
> - **부분 구현**: 일부 기능만 있거나, 다른 경로·방식으로 일부만 지원함 (지금은 QR 로그인·고객 목록 등 로그인/문자 발송에 딸린 것만 남음)
> - **더미**: 뼈대만 남은 엔드포인트. 라우터 경로·요청/응답 스키마·store 함수 시그니처는 있고, 주요 로직(DB 조회·저장, 계산, 검증)은 지웠으며 `backend/app/dummy/`(`DUMMY_ENDPOINTS`)의 고정 응답을 돌려줌. GET은 더미 데이터, 쓰기(POST/PUT/DELETE)는 저장 없이 화면이 깨지지 않는 성공 응답. 라우터·store의 TODO 주석에 구현해야 할 내용이 적혀 있음
> - **미구현**: 서버 API 없음
> - **-**: 기능 제외(뺄) 또는 미착수
>
> **v6 이후 바뀐 점**: 쿠폰함 추가(1-6) / 룰렛 회원당 하루 1회 / 저장소를 새 Supabase 스키마에 맞춤 / 정보 조회(GET)를 더미로 전환(QR 로그인·문자 발송·고객 목록은 제외) / 주문 상태 기능 제거 / **쓰기 API와 통계 계산도 더미로 되돌림(QR 로그인·문자 발송·고객 목록·수신거부 제외)**.
> 되돌림 범위 기준: 문서에서 "구현"·"부분 구현"이던 항목 중 QR 로그인(`/api/auth/*`, `/api/members/me`, `/api/tables/{n}/logins`)과 문자 발송(`/admin/api/marketing/sms/*`)은 유지. 고객 목록·수신거부는 문자 발송 대상과 회원 id를 같이 쓰므로 유지. 쿠폰함·룰렛 하루 1회는 문서에 구현/부분 구현으로 올라 있어 되돌림 대상에 포함(QR 로그인이 쓰는 `coupons.issued_today`만 남김). 새 Supabase 스키마 맞춤은 별도 엔드포인트가 아니라 저장소 코드의 변경이라, 되돌린 저장소는 스키마 정의(SCHEMA)만 남기고 QR·문자 쪽 저장소는 그대로 둠. 이전 코드는 git 기록(`a8b3d14` 이전)에 남아 있어 필요하면 되살릴 수 있음.
> 실제 구현 경로는 `/api/...`(손님), `/admin/api/...`(관리자)이며 v6의 `/api/v1/...`·`/api/admin/...`과 다릅니다. 마지막 열에 실제 경로를 적었습니다. 관리자 인증은 모든 개발 후 마지막에 진행합니다.
> 2026-10-18 갱신: 손님 메뉴 목록(`GET /api/menus`)이 `menus` 테이블 조회로 구현되었습니다. 테스트 실행은 아직 확인되지 않았습니다.

## 구현 현황 집계 (아래 표의 행 기준, 같은 경로가 여러 화면에 나오면 각각 셈)

| 구분 | 행 수 | 해당 |
|---|---|---|
| 구현 | 16 | QR 로그인·카카오·내 정보(6), 태블릿 로그인 기록(1), 수신거부(2), 고객 목록(1), 문자 발송(5), 손님 메뉴 목록(1) |
| 부분 구현 | 4 | 룰렛 상태, 등급별 고객 수(2), 등급 기준 |
| 더미 | 35 | 정보 조회(GET) 19 + 쓰기(POST/PUT/DELETE) 16 (뼈대+TODO) |
| 미구현 | 16 | 서버 API 없음 |
| - (제외·미착수) | 10 | 범위에서 제외 |
| 합계 | 81 | |

## 사용자(고객) 페이지

### 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작)

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/store` | 매장 정보(이름·지점·슬로건·테이블 수) 조회 | 200 | 추가(화면 있음) | 더미 | `GET /api/store`, `/api/v1/store` · 고정 값(dummy.store) |
| ☐ | GET | `/api/v1/roulette/prizes` | 룰렛 칸 구성(라벨·색·종류: 할인율/서비스 메뉴) | 200 | 추가(화면 있음) | 더미 | `GET /api/content/roulette_prizes` · seed/content.json |
| ☐ | GET | `/api/v1/roulette/status` | 남은 룰렛 기회, 로그인한 회원별 룰렛 참여·당첨 상태 | 200 | 추가(화면 있음) | 부분 구현 | `GET /api/tables/{n}/logins`(DB): 이 태블릿 로그인 회원의 룰렛 사용 여부. 남은 기회 계산은 없음 |
| ☐ | POST | `/api/v1/roulette/plays` | 룰렛 돌리기: 서버가 당첨 칸 결정·회원당 1회 검증, 결과(칸 번호·할인율 또는 서비스 메뉴 ID) 반환 | 201 | 유지 | 더미 | `PUT /api/tables/{n}/logins/prize` · 저장·하루 1회(409) 검증·쿠폰 발급 로직 제거, 응답만 더미(dummy.prize_saved). TODO 주석에 규칙 기록 |
| ☐ | POST | `/api/v1/auth/qr` | 테이블 번호로 로그인 QR 발급 | 201 | 추가(화면 있음) | 구현 | `POST /api/auth/qr` (경로가 v1 아님) |
| ☐ | GET | `/api/v1/auth/qr/{secret}` | QR 로그인 진행 상태 조회(폴링) → 완료 시 토큰·회원 정보 | 200 | 추가(화면 있음) | 구현 | `GET /api/auth/qr/{secret}` (+ WebSocket) |
| ☐ | GET | `/api/v1/auth/kakao/start?token=` | QR을 스캔한 휴대폰이 여는 주소: 스캔 처리 후 카카오 로그인으로 이동 | 200 | 추가(화면 있음) | 구현 | `GET /api/auth/kakao/start` |
| ☐ | GET | `/api/v1/auth/kakao/callback` | 카카오 로그인 완료 후 되돌아오는 주소: 회원 생성·로그인 완료 처리 | 200 | 추가(화면 있음) | 구현 | `GET /api/auth/kakao/callback` |
| ☐ | GET | `/api/v1/auth/kakao/continue?token=&agree=` | 휴대폰 로그인 중 "(선택) 광고성 문자 수신 동의" 체크를 세션에 기록하고 카카오 로그인으로 이동 | 302 | 추가(화면 있음) | 구현 | `GET /api/auth/kakao/continue` |
| ☐ | GET | `/api/v1/members/me` | 내 정보 조회: URL 토큰(`?t=`)으로 새로고침 후 로그인 상태 복원 | 200 | 추가(화면 있음) | 구현 | `GET /api/members/me` |

### 1-2. 주문 화면 (카테고리 · 메뉴 · 장바구니 · 주문 확인)

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/categories` | 카테고리 목록 | 200 | 유지 | 더미 | `GET /api/content/categories` |
| ☐ | GET | `/api/v1/menus` | 메뉴 목록(품절 여부·매운맛 단계 포함) | 200 | 유지 | 구현 | `GET /api/menus` · `shop.menus()`가 DB 조회, 메뉴가 비어 있으면 `seed/menu.json`으로 초기화 (테스트 미실행) |
| ☐ | POST | `/api/v1/orders` | 주문 생성(주문 확인 다이얼로그) | 201 | 유지 | 더미 | `POST /api/orders` · 주문·쿠폰 사용 저장 제거, 응답만 더미(dummy.order_created). 주문 상태 기능은 제거됨 |

### 1-3. 주문내역 다이얼로그

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/tables/{tableId}/orders` | 테이블 누적 주문 내역·합계 | 200 | 유지 | 미구현 | 로그인 시각 이후 주문만 합산하는 규칙은 정해졌으나 API 없음 |
| ☐ | GET | `/api/v1/orders/{orderId}` | 주문 상세 | 200 | 뺄(불필요) | - | 범위에서 제외 또는 미착수 |

### 1-4. 직원 호출 다이얼로그

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | POST | `/api/v1/staff-calls` | 필요한 항목(복수 선택)으로 직원 호출 | 201 | 유지 | 더미 | `POST /api/calls` · 저장하지 않고 성공 응답만 돌려줌 (뼈대+TODO) |
| ☐ | GET | `/api/v1/staff-call-items` | 직원 호출 창의 요청 항목 목록(물·수저 등) | 200 | 추가(화면 있음) | 더미 | `GET /api/content/staff_calls` |

### 1-5. AI 질문 · 추천 결과

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/ai/questions` | 추천 질문 목록(단계별 선택지) | 200 | 유지 | 더미 | `GET /api/content/quiz_questions` |
| ☐ | POST | `/api/v1/ai/recommendations` | 답변 + 시간대·날씨로 메뉴 조합 추천, 추천 기록 저장 | 200 | 유지 | 더미 | `POST /api/recommendations` · 노출 기록 저장 제거, 응답만 더미. 조합 계산은 화면에서 함 |
| ☐ | GET | `/api/v1/weather/current` | 현재 날씨(화면에 "날씨 ○○" 표시) | 200 | 추가(화면 있음) | 더미 | `GET /api/content/weather` (고정 값, 실제 날씨 API 아님) |
| ☐ | GET | `/api/v1/ai/recommendation-rules` | 추천 규칙(조합 할인율, 메뉴 짝·음료 구성, 매운맛 조합 구분, 표시 이름) | 200 | 추가(화면 있음) | 더미 | `GET /api/content/rules` |
| ☐ | GET | `/api/v1/ai/preferences/me` | 내 취향·방문 이력 | 200 | 추가(추천) | - | 범위에서 제외 또는 미착수 |
| ☐ | POST | `/api/v1/ai/recommendations/{recommendationId}/alternatives` | 다른 조합 재추천 | 200 | 추가(추천) | - | 범위에서 제외 또는 미착수 |
| ☐ | POST | `/api/v1/ai/recommendations/{recommendationId}/feedback` | 추천 만족도 저장 | 201 | 추가(추천) | - | 범위에서 제외 또는 미착수 |

### 1-6. 쿠폰함 (v7 추가)

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/coupons` | 내 쿠폰 목록(안 쓴 쿠폰 먼저, `used_at`이 null이면 사용 가능) | 200 | 추가(화면 있음) | 더미 | `GET /api/v1/coupons`, `/api/coupons` · dummy.member_coupons |
| ☐ | GET | `/api/tables/{tableNo}/coupons` | 이 태블릿에 로그인한 회원들의 쿠폰함(주문 화면 🎟️ 쿠폰함 팝업) | 200 | 추가(화면 있음) | 더미 | 같은 경로 · dummy.table_coupons. 로그인한 회원만 접근(403) |
| ☐ | PUT | `/api/tables/{tableNo}/logins/prize` | 룰렛 당첨 기록 + 쿠폰함에 쿠폰 발급(하루 1회, 위반 시 409) | 200 | 추가(화면 있음) | 더미 | 같은 경로 · 룰렛 당첨 기록·하루 1회 검증·쿠폰 발급 로직 제거(TODO), 응답만 더미 |
| ☐ | POST | `/api/orders` | 주문 시 `coupon_ids`로 쿠폰 사용 처리(`used_at` 기록) | 201 | 추가(화면 있음) | 더미 | `coupon_ids` 사용 처리 로직 제거(TODO), 요청한 쿠폰 id 를 그대로 사용된 것으로 돌려줌. 유효기간 정책은 미정 |
| ☐ | GET | `/api/tables/{tableNo}/logins` | 새로고침 후 이 태블릿 로그인 회원(룰렛 사용 여부 포함) 복원 | 200 | 추가(화면 있음) | 구현 | 같은 경로 (DB) |
| ☐ | POST | `/api/members/me/opt-out` | 내 광고성 문자 수신거부 | 200 | 추가(화면 있음) | 구현 | 같은 경로 (DB) |

## 관리자 페이지

### 2-1. 로그인

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/owner/me` | 관리자 토큰 검증 · 매장 정보 | 200 | 추가(화면 있음) | 미구현 | 관리자 인증은 개발 마지막에 진행 예정 |

### 2-2. 대시보드

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/admin/stats/sales` | 매출 종합(오늘 주문·평균 주문금액·오늘 신규/재방문 고객·최근 매출) | 200 | 유지 | 더미 | `GET /admin/api/stats` 한 번에 반환 · 계산 로직(services/stats.py) 제거, 고정 값(dummy.dashboard_stats). 오늘 주문·평균 주문금액·신규/재방문만 있음 |
| ☐ | GET | `/api/admin/stats/sales/hourly` | 시간대별 매출 | 200 | 유지 | 미구현 | `GET /admin/api/stats`에 시간대별 매출 없음 |
| ☐ | GET | `/api/admin/stats/sales/trends` | 7일·마지막 영업일·일별 매출 추이 | 200 | 유지 | 미구현 | `GET /admin/api/stats`에 매출 추이 없음 |
| ☐ | GET | `/api/admin/stats/menus/ranking` | 인기 메뉴 TOP10 | 200 | 유지 | 더미 | `GET /admin/api/stats`의 `popular_menus`(더미 주문 기반) |
| ☐ | GET | `/api/admin/customers/grades` | 등급별 고객 수·휴면 수 | 200 | 유지 | 부분 구현 | `GET /admin/api/members`의 회원별 `grade`·`rule`로 집계. 등급별 수 전용 API 없음 |
| ☐ | GET | `/api/admin/alerts` | 휴면·품절 등 운영 알림 | 200 | 유지 | 미구현 |  |
| ☐ | GET | `/api/admin/stats/sales/weekday` | 요일별 매출 | 200 | 추가(화면 있음) | 미구현 | `GET /admin/api/stats`에 요일별 매출 없음 |
| ☐ | GET | `/api/admin/stats/tables` | 테이블 회전율·주문 많은 테이블 TOP5 | 200 | 추가(화면 있음) | 미구현 | 테이블 통계 없음 |
| ☐ | GET | `/api/admin/stats/sales/tickets` | 객단가·주문 금액대 분포·AI 추천/일반 객단가 | 200 | 추가(화면 있음) | 미구현 | 객단가 분포 없음(평균 주문금액만 `stats`에 있음) |
| ☐ | GET | `/api/admin/stats/customers` | 연령대·성별 분포, 회원 주문 비중, 상위 고객 TOP5 | 200 | 추가(화면 있음) | 더미 | `GET /admin/api/stats` 의 `age_groups`·`genders`(고정 값). 상위 고객 TOP5 없음 |
| ☐ | GET | `/api/admin/stats/ai-recommendations` | AI 추천 노출 수·적중률 | 200 | 추가(화면 있음) | 더미 | `GET /admin/api/stats`의 `ai`(더미 입력) |
| ☐ | GET | `/api/admin/stats/sales/categories` | 메뉴군 매출 | 200 | 뺄(화면 없음) | - | 범위에서 제외 또는 미착수 |
| ☐ | GET | `/api/admin/stats/menus/changes` | 전월 대비 메뉴 증감 | 200 | 뺄(화면 없음) | - | 범위에서 제외 또는 미착수 |
| ☐ | GET | `/api/admin/stats/menus/weather` | 날씨별 메뉴 판매 | 200 | 뺄(화면 없음) | - | 범위에서 제외 또는 미착수 |
| ☐ | GET | `/api/admin/stats/weather-sales` | 날씨별 매출 비교 | 200 | 뺄(화면 없음) | - | 범위에서 제외 또는 미착수 |
| ☐ | GET | `/api/admin/stats/grade-menus` | 등급별 주문 메뉴 | 200 | 뺄(화면 없음) | - | 범위에서 제외 또는 미착수 |
| ☐ | PATCH | `/api/admin/alerts/{alertId}` | 알림 확인 처리 | 200 | 추가(추천) | - | 범위에서 제외 또는 미착수 |

### 2-3. 메뉴 관리

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/owner/menus` | 관리자용 메뉴 목록(비공개·품절 포함) | 200 | 추가(화면 있음) | 더미 | `GET /admin/api/menus` (더미 목록) |
| ☐ | POST | `/api/v1/owner/menus` | 메뉴 등록(이름·가격·설명·이미지·매운맛·가중치·세트 가능) | 201 | 유지 | 더미 | `PUT /admin/api/menus/{id}` · 저장 제거, 보낸 값을 반영한 메뉴를 돌려줌(dummy.menu_saved) |
| ☐ | PATCH | `/api/v1/owner/menus/{menuId}` | 메뉴 수정(가격·설명·판매 여부·매운맛 등) | 200 | 유지 | 더미 | `PUT /admin/api/menus/{id}` · 저장 제거, 응답만 더미 |
| ☐ | DELETE | `/api/v1/owner/menus/{menuId}` | 메뉴 삭제 | 204 | 유지 | 더미 | `DELETE /admin/api/menus/{id}` · 아무것도 지우지 않고 204 |
| ☐ | GET | `/api/v1/categories` | 카테고리 목록(메뉴 개수 포함) | 200 | 유지 | 더미 | `GET /api/content/categories` (메뉴 개수는 없음) |
| ☐ | POST | `/api/v1/owner/categories` | 카테고리 추가(이름·아이콘·색상) | 201 | 추가(화면 있음) | 더미 | `PUT /admin/api/content/categories` 로 목록 통째 교체 · 저장 제거, 받은 값을 그대로 돌려줌 |
| ☐ | PATCH | `/api/v1/owner/categories/{categoryId}` | 카테고리 수정 | 200 | 추가(화면 있음) | 더미 | `PUT /admin/api/content/categories` 로 목록 통째 교체 · 저장 제거 |
| ☐ | DELETE | `/api/v1/owner/categories/{categoryId}` | 카테고리 삭제(메뉴가 있으면 불가) | 204 | 추가(화면 있음) | 더미 | `PUT /admin/api/content/categories` 로 목록 통째 교체 · 저장 제거 (메뉴 있으면 불가 검증 없음) |

### 2-4. 추천 가중치

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/owner/menus` | 메뉴와 현재 가중치 조회 | 200 | 추가(화면 있음) | 더미 | `GET /admin/api/menus` (더미 목록) |
| ☐ | PATCH | `/api/v1/owner/menus/{menuId}` | 가중치 단건 변경 | 200 | 유지 | 더미 | `PUT /admin/api/menus/{id}` · 저장 제거, 응답만 더미 |
| ☐ | PATCH | `/api/v1/owner/menus/weights` | 여러 메뉴 가중치 일괄 저장 | 200 | 추가(화면 있음) | 더미 | 메뉴별 `PUT /admin/api/menus/{id}`의 `weight`를 여러 번 호출(저장 제거, 응답만 더미). 일괄 API 없음 |

### 2-5. 이벤트 (룰렛 설정)

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/roulette/prizes` | 룰렛 칸 구성·확률 가중치 조회(이벤트 화면 표) | 200 | 추가(화면 있음) | 더미 | `GET /api/content/roulette_prizes` |
| ☐ | PUT | `/api/v1/owner/roulette/prizes` | 룰렛 칸 구성·확률 가중치 저장(칸 2~8개, 가중치 합 0 초과 검증) | 200 | 추가(화면 있음) | 더미 | `PUT /admin/api/content/roulette_prizes` · 칸 2~8개·가중치 검증과 저장 제거(TODO에 규칙 기록), 받은 값을 그대로 돌려줌 |

### 2-6. 고객 등급

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/admin/customers` | 고객 목록(등급 기준을 쿼리로 미리 적용) | 200 | 유지 | 구현 | `GET /admin/api/members` (DB, 등급 기준 쿼리 지원) |
| ☐ | GET | `/api/admin/customers/grades` | 등급별 고객 수 | 200 | 유지 | 부분 구현 | `GET /admin/api/members`의 회원별 `grade`·`rule`로 집계. 등급별 수 전용 API 없음 |
| ☐ | GET | `/api/admin/customers/grades/rules` | 등급 기준 조회 | 200 | 유지 | 부분 구현 | `GET /admin/api/members` 응답의 `rule` |

### 2-7. 주문 이력

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/v1/owner/orders` | 주문 목록(기간·테이블·메뉴·금액·고객 조건) | 200 | 유지 | 더미 | `GET /admin/api/orders` (더미 주문) |

### 2-9. 마케팅 › AI 문자

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/admin/marketing/sms/usage` | 월 문자 사용량·무료 한도 | 200 | 추가(화면 있음) | 구현 | `GET /admin/api/marketing/sms/usage` |
| ☐ | POST | `/api/admin/marketing/sms/preview` | 대상 등급·본문으로 대상 수·비용·발송 가능 여부 미리보기 | 200 | 추가(화면 있음) | 구현 | `POST /admin/api/marketing/sms/preview` |
| ☐ | POST | `/api/admin/marketing/sms/candidates` | AI 문자 후보 여러 개 생성: 키워드(휴면·단골·주문·날씨·행사·가중치 조합)별 수신 등급 + 문구 + 출처(ai/template) | 200 | 추가(화면 있음) | 미구현 |  |
| ☐ | POST | `/api/admin/marketing/sms/send` | 즉시 발송 또는 예약 발송 | 201 | 추가(화면 있음) | 구현 | `POST /admin/api/marketing/sms/send` (솔라피) |
| ☐ | POST | `/api/admin/marketing/sms/logs/{logId}/cancel` | 예약 발송 취소 | 200 | 추가(화면 있음) | 구현 | `POST /admin/api/marketing/sms/logs/{id}/cancel` |
| ☐ | GET | `/api/admin/marketing/sms/logs` | 발송·예약 기록 | 200 | 추가(화면 있음) | 구현 | `GET /admin/api/marketing/sms/logs` |
| ☐ | POST | `/api/admin/customers/{customerId}/opt-out` | 회원 수신거부 등록 | 200 | 추가(화면 있음) | 구현 | `POST /admin/api/members/{id}/opt-out` |
| ☐ | GET | `/api/admin/marketing/external-context` | 오늘 날씨·지역 행사 문구(AI 문자 후보에 사용) | 200 | 추가(추천) | 미구현 |  |

### 2-10. 마케팅 › AI 챗봇 · AI 추천

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/admin/marketing/opportunities?round=` | AI 마케팅 추천 카드(제목·근거·행동). 화면의 "🔄 재추천"은 `round`(또는 `page`)를 올려 다음 묶음(4개씩, 끝나면 처음으로)을 받음 | 200 | 유지 | 미구현 |  |
| ☐ | POST | `/api/admin/marketing/chat/sessions` | 챗봇 대화 세션 생성(첫 인사 메시지 포함) | 201 | 추가(추천) | 미구현 |  |
| ☐ | GET | `/api/admin/marketing/chat/sessions` | 내 대화 세션 목록(최근순, 제목·마지막 메시지 시각) | 200 | 추가(추천) | 미구현 |  |
| ☐ | GET | `/api/admin/marketing/chat/sessions/{sessionId}` | 대화 세션 조회: 메시지 전체(역할·내용·시각) | 200 | 추가(추천) | 미구현 |  |
| ☐ | POST | `/api/admin/marketing/chat/sessions/{sessionId}/messages` | 질문 전송 → 답변. 예: "오늘 매출 얼마야" | 201 | 추가(화면 있음) | 미구현 |  |
| ☐ | DELETE | `/api/admin/marketing/chat/sessions/{sessionId}` | 대화 세션 삭제(대화 지우기) | 204 | 추가(추천) | 미구현 |  |

### 2-11. 직원 호출 관리 (v7 추가)

| 채택 | 메서드 | 경로 | 설명 | 성공 응답 | 구분 | 구현 현황 | 실제 경로 · 비고 |
|---|---|---|---|---|---|---|---|
| ☐ | GET | `/api/admin/calls` | 직원 호출 목록 | 200 | 추가(화면 있음) | 더미 | `GET /admin/api/calls` · dummy.calls |
| ☐ | POST | `/api/admin/calls/{callId}/done` | 호출 처리 완료 | 200 | 추가(화면 있음) | 더미 | `POST /admin/api/calls/{id}/done` · 저장 제거, 완료된 호출을 돌려줌 |
