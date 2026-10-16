# F&BGrowth API 담당 분배 (5명, 3:2:2:2:1, 파일 충돌 최소화)

## 경로 표기

| 표기 | 실제 위치 |
|---|---|
| `B/` | `backend/app/` (서버) |
| `A/` | `admin/` (관리자 Streamlit) |
| `U/` | `user/` (손님 Streamlit) |
| `T/` | 저장소 루트 `tests/` (화면+통합 테스트) |
| `BT/` | `backend/tests/` (서버 테스트) |
| (신규) | 지금 없는 파일. 담당자가 새로 만든다. 새 파일은 본인만 쓰므로 충돌이 없다 |

## 담당별 요약

| 담당 | 비율 | 맡는 범위 | API 행 수 | 구현 | 부분 구현 | 더미 | 미구현 |
|---|---|---|---|---|---|---|---|
| 성호 | 3 | QR 로그인 · 문자 발송 · 관리자 로그인 · 관리자 AI 챗봇 | 21 | 13 | 0 | 0 | 8 |
| 재현 | 2 | 손님 AI 추천 질문 · 룰렛 · 쿠폰 · 주문(주문 이력 포함) | 14 | 0 | 1 | 12 | 1 |
| 수용 | 2 | 관리자 대시보드 · 고객 등급(수신거부 포함) | 15 | 2 | 3 | 4 | 6 |
| 서준 | 2 | 메뉴 · 카테고리 · 추천 가중치 | 13 | 0 | 0 | 13 | 0 |
| 석원 | 1 | 관리자 AI 추천 · 직원 호출 · 룰렛 설정 | 8 | 0 | 0 | 7 | 1 |
| 합계 | 10 | | 71 | | | | |

## 이전 분배에서 바뀐 곳

| 항목 | 이전 담당 | 지금 담당 | 바꾼 이유 |
|---|---|---|---|
| 주문 이력 `GET /api/v1/owner/orders` | 서준 | 재현 | 주문 저장소(`B/stores/shop_orders.py`)를 주문 생성·테이블 누적 주문과 한 사람이 쓰게 하려고 |
| 회원 수신거부 `POST /api/admin/customers/{customerId}/opt-out` | 성호 | 수용 | 같은 라우터 파일(`B/routers/admin/members.py`)을 고객 등급과 한 사람이 쓰게 하려고. 이미 구현이라 코드 수정은 거의 없음 |
| 손님 쿠폰 사용 `POST /api/orders` | 재현 | 재현(유지) | `POST /api/v1/orders`와 같은 함수라 한 사람이 처리 |

## 성호 (비율 3) · QR 로그인 · 문자 발송 · 관리자 로그인 · 관리자 AI 챗봇

| 화면 | 메서드 | 경로 | 설명 | 구현 현황 | 수정할 주요 파일 |
|---|---|---|---|---|---|
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | POST | `/api/v1/auth/qr` | 테이블 번호로 로그인 QR 발급 | 구현 | `B/routers/auth.py` `B/stores/login_sessions.py` (수정 거의 없음) |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/auth/qr/{secret}` | QR 로그인 진행 상태 조회(폴링) → 완료 시 토큰·회원 정보 | 구현 | `B/routers/auth.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/auth/kakao/start?token=` | QR을 스캔한 휴대폰이 여는 주소: 스캔 처리 후 카카오 로그인으로 이동 | 구현 | `B/routers/auth.py` `B/services/kakao.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/auth/kakao/callback` | 카카오 로그인 완료 후 되돌아오는 주소: 회원 생성·로그인 완료 처리 | 구현 | `B/routers/auth.py` `B/stores/members.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/auth/kakao/continue?token=&agree=` | 휴대폰 로그인 중 "(선택) 광고성 문자 수신 동의" 체크를 세션에 기록하고 카카오 로그인으로 이동 | 구현 | `B/routers/auth.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/members/me` | 내 정보 조회: URL 토큰(`?t=`)으로 새로고침 후 로그인 상태 복원 | 구현 | `B/routers/user.py` (수정 없음, 읽기만) |
| 1-6. 쿠폰함 (v7 추가) | GET | `/api/tables/{tableNo}/logins` | 새로고침 후 이 태블릿 로그인 회원(룰렛 사용 여부 포함) 복원 | 구현 | `B/routers/user.py` (수정 없음, 읽기만) |
| 1-6. 쿠폰함 (v7 추가) | POST | `/api/members/me/opt-out` | 내 광고성 문자 수신거부 | 구현 | `B/routers/user.py` (수정 없음, 읽기만) |
| 2-1. 로그인 | GET | `/api/v1/owner/me` | 관리자 토큰 검증 · 매장 정보 | 미구현 | `B/routers/admin/owner.py`(신규) `B/services/supabase_auth.py` `B/core/dependencies.py` `A/views/login.py` |
| 2-9. 마케팅 › AI 문자 | GET | `/api/admin/marketing/sms/usage` | 월 문자 사용량·무료 한도 | 구현 | `B/routers/admin/sms.py` `B/services/sms.py` (수정 거의 없음) |
| 2-9. 마케팅 › AI 문자 | POST | `/api/admin/marketing/sms/preview` | 대상 등급·본문으로 대상 수·비용·발송 가능 여부 미리보기 | 구현 | `B/routers/admin/sms.py` `B/services/sms.py` |
| 2-9. 마케팅 › AI 문자 | POST | `/api/admin/marketing/sms/candidates` | AI 문자 후보 여러 개 생성: 키워드(휴면·단골·주문·날씨·행사·가중치 조합)별 수신 등급 + 문구 + 출처(ai/template) | 미구현 | `B/routers/admin/sms.py` `A/marketing_ai.py`(문자 후보 함수) `A/views/marketing.py`(AI 문자 탭) |
| 2-9. 마케팅 › AI 문자 | POST | `/api/admin/marketing/sms/send` | 즉시 발송 또는 예약 발송 | 구현 | `B/routers/admin/sms.py` `B/services/sms.py` `B/stores/sms_logs.py` |
| 2-9. 마케팅 › AI 문자 | POST | `/api/admin/marketing/sms/logs/{logId}/cancel` | 예약 발송 취소 | 구현 | `B/routers/admin/sms.py` |
| 2-9. 마케팅 › AI 문자 | GET | `/api/admin/marketing/sms/logs` | 발송·예약 기록 | 구현 | `B/routers/admin/sms.py` |
| 2-9. 마케팅 › AI 문자 | GET | `/api/admin/marketing/external-context` | 오늘 날씨·지역 행사 문구(AI 문자 후보에 사용) | 미구현 | `B/routers/admin/external.py`(신규) · 날씨 조회는 재현의 `B/services/weather.py`를 가져다 씀(수정 안 함) |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | POST | `/api/admin/marketing/chat/sessions` | 챗봇 대화 세션 생성(첫 인사 메시지 포함) | 미구현 | `B/routers/admin/chat.py`(신규) `B/stores/chat.py`(신규) |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | GET | `/api/admin/marketing/chat/sessions` | 내 대화 세션 목록(최근순, 제목·마지막 메시지 시각) | 미구현 | `B/routers/admin/chat.py` `B/stores/chat.py` |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | GET | `/api/admin/marketing/chat/sessions/{sessionId}` | 대화 세션 조회: 메시지 전체(역할·내용·시각) | 미구현 | `B/routers/admin/chat.py` `B/stores/chat.py` |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | POST | `/api/admin/marketing/chat/sessions/{sessionId}/messages` | 질문 전송 → 답변. 예: "오늘 매출 얼마야" | 미구현 | `B/routers/admin/chat.py` `B/services/chat.py`(신규) `A/views/marketing.py`(AI 챗봇 탭) |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | DELETE | `/api/admin/marketing/chat/sessions/{sessionId}` | 대화 세션 삭제(대화 지우기) | 미구현 | `B/routers/admin/chat.py` `B/stores/chat.py` |

## 재현 (비율 2) · 손님 AI 추천 질문 · 룰렛 · 쿠폰 · 주문

| 화면 | 메서드 | 경로 | 설명 | 구현 현황 | 수정할 주요 파일 |
|---|---|---|---|---|---|
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/store` | 매장 정보(이름·지점·슬로건·테이블 수) 조회 | 더미 | `B/routers/user.py`(`/store` 함수) `B/stores/store_info.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/roulette/status` | 남은 룰렛 기회, 로그인한 회원별 룰렛 참여·당첨 상태 | 부분 구현 | `B/routers/roulette.py`(신규) `B/stores/tablet_logins.py` `U/state/roulette.py` |
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | POST | `/api/v1/roulette/plays` | 룰렛 돌리기: 서버가 당첨 칸 결정·회원당 1회 검증, 결과(칸 번호·할인율 또는 서비스 메뉴 ID) 반환 | 더미 | `B/routers/roulette.py` `B/stores/coupons.py` `U/ui/roulette.py` `U/views/splash.py` |
| 1-2. 주문 화면 (카테고리 · 메뉴 · 장바구니 · 주문 확인) | POST | `/api/v1/orders` | 주문 생성(주문 확인 다이얼로그) | 더미 | `B/routers/user.py`(`/orders` 함수) `B/stores/shop_orders.py` `U/state/cart.py` |
| 1-3. 주문내역 다이얼로그 | GET | `/api/v1/tables/{tableId}/orders` | 테이블 누적 주문 내역·합계 | 미구현 | `B/routers/orders.py`(신규) `B/stores/shop_orders.py` `U/ui/dialogs.py` |
| 1-5. AI 질문 · 추천 결과 | GET | `/api/v1/ai/questions` | 추천 질문 목록(단계별 선택지) | 더미 | `B/routers/ai.py`(신규) `U/views/ai.py` `U/state/quiz.py` `U/ai_quiz_data.py` |
| 1-5. AI 질문 · 추천 결과 | POST | `/api/v1/ai/recommendations` | 답변 + 시간대·날씨로 메뉴 조합 추천, 추천 기록 저장 | 더미 | `B/routers/ai.py` `B/stores/shop_recommendations.py` `U/recommendations.py` |
| 1-5. AI 질문 · 추천 결과 | GET | `/api/v1/weather/current` | 현재 날씨(화면에 "날씨 ○○" 표시) | 더미 | `B/routers/ai.py` `B/services/weather.py`(신규, 성호도 가져다 씀) |
| 1-5. AI 질문 · 추천 결과 | GET | `/api/v1/ai/recommendation-rules` | 추천 규칙(조합 할인율, 메뉴 짝·음료 구성, 매운맛 조합 구분, 표시 이름) | 더미 | `B/routers/ai.py` `U/recommendation_data.py` |
| 1-6. 쿠폰함 (v7 추가) | GET | `/api/v1/coupons` | 내 쿠폰 목록(안 쓴 쿠폰 먼저, `used_at`이 null이면 사용 가능) | 더미 | `B/routers/user.py`(`/coupons` 함수) `B/stores/coupons.py` |
| 1-6. 쿠폰함 (v7 추가) | GET | `/api/tables/{tableNo}/coupons` | 이 태블릿에 로그인한 회원들의 쿠폰함(주문 화면 🎟️ 쿠폰함 팝업) | 더미 | `B/routers/user.py` `B/stores/coupons.py` `U/state/coupons.py` `U/ui/coupons.py` |
| 1-6. 쿠폰함 (v7 추가) | PUT | `/api/tables/{tableNo}/logins/prize` | 룰렛 당첨 기록 + 쿠폰함에 쿠폰 발급(하루 1회, 위반 시 409) | 더미 | `B/routers/user.py` `B/stores/tablet_logins.py`(`set_prize`) `B/stores/coupons.py` |
| 1-6. 쿠폰함 (v7 추가) | POST | `/api/orders` | 주문 시 `coupon_ids`로 쿠폰 사용 처리(`used_at` 기록) | 더미 | `B/routers/user.py` `B/stores/coupons.py`(`use`) |
| 2-7. 주문 이력 | GET | `/api/v1/owner/orders` | 주문 목록(기간·테이블·메뉴·금액·고객 조건) | 더미 | `B/routers/admin/orders.py` `B/stores/shop_orders.py` `A/views/orders.py` `A/order_filters.py` |

## 수용 (비율 2) · 관리자 대시보드 · 고객 등급

| 화면 | 메서드 | 경로 | 설명 | 구현 현황 | 수정할 주요 파일 |
|---|---|---|---|---|---|
| 2-2. 대시보드 | GET | `/api/admin/stats/sales` | 매출 종합(오늘 주문·평균 주문금액·오늘 신규/재방문 고객·최근 매출) | 더미 | `B/routers/admin/stats.py` `B/services/stats.py` `B/stores/stats.py`(신규, 주문 읽기 SQL) `A/views/dashboard.py` `A/dashboard_stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/sales/hourly` | 시간대별 매출 | 미구현 | `B/routers/admin/stats.py` `B/stores/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/sales/trends` | 7일·마지막 영업일·일별 매출 추이 | 미구현 | `B/routers/admin/stats.py` `B/stores/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/menus/ranking` | 인기 메뉴 TOP10 | 더미 | `B/routers/admin/stats.py` `B/services/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/customers/grades` | 등급별 고객 수·휴면 수 | 부분 구현 | `B/routers/admin/members.py` `B/services/grades.py` |
| 2-2. 대시보드 | GET | `/api/admin/alerts` | 휴면·품절 등 운영 알림 | 미구현 | `B/routers/admin/alerts.py`(신규) `A/views/dashboard.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/sales/weekday` | 요일별 매출 | 미구현 | `B/routers/admin/stats.py` `B/stores/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/tables` | 테이블 회전율·주문 많은 테이블 TOP5 | 미구현 | `B/routers/admin/stats.py` `B/stores/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/sales/tickets` | 객단가·주문 금액대 분포·AI 추천/일반 객단가 | 미구현 | `B/routers/admin/stats.py` `B/stores/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/customers` | 연령대·성별 분포, 회원 주문 비중, 상위 고객 TOP5 | 더미 | `B/routers/admin/stats.py` `B/services/stats.py` |
| 2-2. 대시보드 | GET | `/api/admin/stats/ai-recommendations` | AI 추천 노출 수·적중률 | 더미 | `B/routers/admin/stats.py` `B/services/stats.py` |
| 2-6. 고객 등급 | GET | `/api/admin/customers` | 고객 목록(등급 기준을 쿼리로 미리 적용) | 구현 | `B/routers/admin/members.py` `A/views/customers.py` |
| 2-6. 고객 등급 | GET | `/api/admin/customers/grades` | 등급별 고객 수 | 부분 구현 | `B/routers/admin/members.py` `B/services/grades.py` |
| 2-6. 고객 등급 | GET | `/api/admin/customers/grades/rules` | 등급 기준 조회 | 부분 구현 | `B/routers/admin/members.py` `B/routers/admin/common.py` |
| 2-9. 마케팅 › AI 문자 | POST | `/api/admin/customers/{customerId}/opt-out` | 회원 수신거부 등록 | 구현 | `B/routers/admin/members.py` (수정 거의 없음) |

## 서준 (비율 2) · 메뉴 · 카테고리 · 추천 가중치

| 화면 | 메서드 | 경로 | 설명 | 구현 현황 | 수정할 주요 파일 |
|---|---|---|---|---|---|
| 1-2. 주문 화면 (카테고리 · 메뉴 · 장바구니 · 주문 확인) | GET | `/api/v1/categories` | 카테고리 목록 | 더미 | `B/routers/menus.py`(신규) `B/stores/shop_menus.py` `U/menu_data.py` `U/state/menu_groups.py` |
| 1-2. 주문 화면 (카테고리 · 메뉴 · 장바구니 · 주문 확인) | GET | `/api/v1/menus` | 메뉴 목록(품절 여부·매운맛 단계 포함) | 더미 | `B/routers/user.py`(`/menus` 함수) `B/stores/shop_menus.py` `B/seed/menu.json` `U/views/order.py` `U/menu_images.py` |
| 2-3. 메뉴 관리 | GET | `/api/v1/owner/menus` | 관리자용 메뉴 목록(비공개·품절 포함) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` `A/views/menu.py` |
| 2-3. 메뉴 관리 | POST | `/api/v1/owner/menus` | 메뉴 등록(이름·가격·설명·이미지·매운맛·가중치·세트 가능) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | PATCH | `/api/v1/owner/menus/{menuId}` | 메뉴 수정(가격·설명·판매 여부·매운맛 등) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | DELETE | `/api/v1/owner/menus/{menuId}` | 메뉴 삭제 | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | GET | `/api/v1/categories` | 카테고리 목록(메뉴 개수 포함) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | POST | `/api/v1/owner/categories` | 카테고리 추가(이름·아이콘·색상) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | PATCH | `/api/v1/owner/categories/{categoryId}` | 카테고리 수정 | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-3. 메뉴 관리 | DELETE | `/api/v1/owner/categories/{categoryId}` | 카테고리 삭제(메뉴가 있으면 불가) | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-4. 추천 가중치 | GET | `/api/v1/owner/menus` | 메뉴와 현재 가중치 조회 | 더미 | `B/routers/admin/menus.py` `A/views/weights.py` |
| 2-4. 추천 가중치 | PATCH | `/api/v1/owner/menus/{menuId}` | 가중치 단건 변경 | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |
| 2-4. 추천 가중치 | PATCH | `/api/v1/owner/menus/weights` | 여러 메뉴 가중치 일괄 저장 | 더미 | `B/routers/admin/menus.py` `B/stores/shop_menus.py` |

## 석원 (비율 1) · 관리자 AI 추천 · 직원 호출 · 룰렛 설정

| 화면 | 메서드 | 경로 | 설명 | 구현 현황 | 수정할 주요 파일 |
|---|---|---|---|---|---|
| 1-1. 스플래시 (룰렛 · 로그인 · 주문 시작) | GET | `/api/v1/roulette/prizes` | 룰렛 칸 구성(라벨·색·종류: 할인율/서비스 메뉴) | 더미 | `B/routers/roulette_prizes.py`(신규) `B/stores/roulette_prizes.py`(신규, 재현이 읽기만 함) |
| 1-4. 직원 호출 다이얼로그 | POST | `/api/v1/staff-calls` | 필요한 항목(복수 선택)으로 직원 호출 | 더미 | `B/routers/staff_calls.py`(신규) `B/stores/shop_calls.py` `U/ui/dialogs.py`의 직원 호출 부분 |
| 1-4. 직원 호출 다이얼로그 | GET | `/api/v1/staff-call-items` | 직원 호출 창의 요청 항목 목록(물·수저 등) | 더미 | `B/routers/staff_calls.py` `B/stores/shop_calls.py` |
| 2-5. 이벤트 (룰렛 설정) | GET | `/api/v1/roulette/prizes` | 룰렛 칸 구성·확률 가중치 조회(이벤트 화면 표) | 더미 | `B/routers/roulette_prizes.py` `A/views/events.py` |
| 2-5. 이벤트 (룰렛 설정) | PUT | `/api/v1/owner/roulette/prizes` | 룰렛 칸 구성·확률 가중치 저장(칸 2~8개, 가중치 합 0 초과 검증) | 더미 | `B/routers/roulette_prizes.py` `B/stores/roulette_prizes.py` `A/views/events.py` |
| 2-10. 마케팅 › AI 챗봇 · AI 추천 | GET | `/api/admin/marketing/opportunities?round=` | AI 마케팅 추천 카드(제목·근거·행동). 화면의 "🔄 재추천"은 `round`(또는 `page`)를 올려 다음 묶음(4개씩, 끝나면 처음으로)을 받음 | 미구현 | `B/routers/admin/opportunities.py`(신규) `A/marketing_ai.py`(추천 함수) `A/views/marketing.py`(AI 추천 탭) |
| 2-11. 직원 호출 관리 (v7 추가) | GET | `/api/admin/calls` | 직원 호출 목록 | 더미 | `B/routers/admin/calls.py`(신규) `B/stores/shop_calls.py` |
| 2-11. 직원 호출 관리 (v7 추가) | POST | `/api/admin/calls/{callId}/done` | 호출 처리 완료 | 더미 | `B/routers/admin/calls.py` `B/stores/shop_calls.py` |

## 어쩔 수 없이 같이 건드리는 파일

| 파일 | 건드리는 사람 | 충돌 위험 | 충돌을 줄이는 방법 |
|---|---|---|---|
| `B/dummy.py` (`DUMMY_ENDPOINTS` 포함) | 재현·수용·서준·석원 | 높음: 더미 함수와 `DUMMY_ENDPOINTS` 줄이 한 파일에 붙어 있어, 이웃한 줄을 지우면 충돌 | 각자 본인 함수와 본인 `DUMMY_ENDPOINTS` 줄만 지우고, 빈 줄·이웃 줄은 건드리지 않음. 작업마다 PR을 작게 만들어 자주 머지하고, 머지 전에 `dev`를 먼저 받아 옴. 근본 해결은 아래 "코드 분리 제안" 1번 |
| `B/routers/user.py` | 재현(`/store`·`/orders`·`/coupons`·쿠폰함·당첨), 서준(`/menus`), 석원(`/calls`·`/content`의 룰렛·직원 호출 항목) | 중간: 함수 단위로는 겹치지 않지만 맨 위 import와 `OrderIn`·`CallIn` 같은 모델이 붙어 있음 | 새 엔드포인트는 위 표의 (신규) 라우터 파일에 만들고, `user.py`에서는 본인 함수만 지움. import 줄 추가는 한 줄씩만, 모델은 본인 것만 수정 |
| `B/factory.py` 와 `B/routers/admin/__init__.py` | 신규 라우터를 만드는 모두 | 중간: 등록 줄을 같은 위치에 한 줄씩 추가하므로 충돌 | 성호가 선작업으로 (신규) 라우터 파일을 빈 틀로 만들어 등록까지 한 번에 머지(아래 "코드 분리 제안" 2번). 그 뒤로는 이 두 파일을 아무도 수정하지 않음 |
| `B/routers/admin/content.py` , `GET /api/content` , `B/seed/content.json` | 서준(카테고리), 석원(룰렛·직원 호출 항목), 재현(AI 질문·날씨·추천 규칙) | 중간: 6가지 콘텐츠가 한 JSON·한 엔드포인트에 있음 | 각자 자기 항목을 새 엔드포인트로 옮기고 JSON에서는 본인 항목 키만 지움. 모든 항목이 옮겨지면 서준이 마지막에 `content.py`·`content.json`을 삭제 |
| `B/stores/shop_orders.py` | 재현(주문 생성·누적·이력) | 낮음: 재현 혼자 씀 | 수용의 통계는 이 파일을 고치지 않고 `B/stores/stats.py`(신규)에서 읽기 SQL을 따로 만듦 |
| `B/stores/tablet_logins.py` , `B/stores/coupons.py` | 재현(`set_prize`·쿠폰 발급·사용), 성호(`auth.py`가 `record`·`issued_today`를 부름) | 낮음: 성호는 호출만 하고 수정하지 않음 | 두 파일은 재현만 수정. 성호는 함수 이름·시그니처가 바뀌면 재현이 미리 알림 |
| `B/stores/shop_calls.py` | 석원 | 낮음 | 석원 혼자 씀 |
| `B/stores/roulette_prizes.py`(신규) | 석원이 만들고 재현이 읽음 | 낮음: 재현은 호출만 함 | 석원이 `list()` 함수 시그니처를 먼저 정해 재현에게 알림 |
| `B/services/weather.py`(신규) | 재현이 만들고 성호가 읽음 | 낮음 | 재현이 날씨 조회를 먼저 만들고 성호가 import만 함 |
| `B/services/stats.py` | 수용이 만들고 성호 챗봇("오늘 매출 얼마야")이 읽음 | 낮음 | 수용만 수정, 성호는 호출만 함 |
| `A/admin_repository.py` (`ApiBackend` 클래스와 `AdminRepository`에 모든 관리자 호출이 한 파일) | 성호·수용·서준·석원·재현(주문 이력) | 높음 | 본인 기능의 메서드 블록 끝에만 추가하고 기존 메서드 순서·들여쓰기는 건드리지 않음. 담당 구역 주석(`# ---- 메뉴 ----` 등)을 기준으로 자기 구역 안에서만 수정 |
| `A/views/marketing.py` , `A/marketing_ai.py` | 성호(AI 문자·AI 챗봇 탭), 석원(AI 추천 탭) | 중간: 탭별 함수는 분리돼 있지만 파일이 하나 | 성호는 `marketing_dashboard`·`marketing_chatbot_tab`·문자 후보 함수만, 석원은 `marketing_recommend_tab`·`recommend`·`next_rec_round`·`pick_recommendations`만 수정. 파일 분리는 "코드 분리 제안" 3번 |
| `A/app.py` | 새 화면이 생길 때만 | 낮음: 화면 파일이 이미 담당별로 나뉘어 있어 거의 안 건드림 | 새 화면 추가가 필요하면 성호가 한 번에 처리 |
| `U/user_repository.py` | 재현(주문·추천), 석원(직원 호출), 서준(메뉴 불러오기 `load_content`) | 중간: 한 클래스 3개에 메서드가 같은 순서로 반복됨 | 본인 기능의 메서드만 수정하고, 새 메서드는 파일 끝에 추가 |
| `U/app.py` | 거의 없음 | 낮음 | 진입점이라 수정하지 않음 |
| `BT/test_dummy_get.py` , `BT/test_shop_admin.py` , `T/test_data_source.py` , `T/test_admin_data_source.py` , `T/test_qr_login_e2e.py` | 해당 기능을 교체하는 모두 (`skip` 제거 때문) | 중간: 한 파일에 여러 담당의 테스트가 섞임 | 본인 테스트 함수의 `skip` 줄만 지우고, 새 테스트는 본인 이름의 새 파일(예: `BT/test_roulette.py`)에 작성 |
| `docs/DB_SCHEMA.md` , `docs/db/fbgrowth_schema.sql` , `AGENTS.md` | 스키마·규칙을 바꾸는 사람 | 낮음~중간: 드물게만 수정 | 스키마를 바꾸면 해당 변경을 먼저 팀에 알리고, 표 한 구역만 수정하는 작은 PR로 먼저 머지 |

## 코드 분리 제안 (이번에는 실행하지 않음, 승인 시 선작업 PR 하나로 처리)

| 번호 | 제안 | 줄이는 충돌 | 담당·시점 |
|---|---|---|---|
| 1 | `B/dummy.py`를 `B/dummy/` 폴더로 나눠 담당 기능별 파일(`menus.py`, `orders.py`, `stats.py` 등)로 쪼개고, `DUMMY_ENDPOINTS`도 파일별로 둠 | `dummy.py`의 가장 큰 충돌 지점 해소 | 성호, 다른 사람이 구현을 시작하기 전에 먼저 머지 |
| 2 | `B/routers/user.py`를 기능별 라우터(`menus`, `orders`, `coupons`, `roulette`, `staff_calls`, `ai`)로 쪼개고, (신규) 라우터 파일을 빈 틀로 만들어 `factory.py`·`admin/__init__.py`에 한 번에 등록 | `user.py`, `factory.py`, `admin/__init__.py` 충돌 해소 | 성호, 1번과 같은 PR |
| 3 | `A/views/marketing.py`와 `A/marketing_ai.py`를 `marketing_sms`·`marketing_chat`·`marketing_recommend`로 쪼갬 | 성호와 석원의 같은 파일 수정 해소 | 성호, 1번과 같은 PR 또는 바로 뒤 |
| 4 | `A/admin_repository.py`의 `ApiBackend`를 기능별 믹스인 파일로 쪼갬 | 관리자 호출 모음 파일 충돌 해소 | 수용, 1~3번 머지 뒤 |
