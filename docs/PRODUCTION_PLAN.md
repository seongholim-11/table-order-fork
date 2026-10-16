# 정식 구현 계획: QR 로그인 · 솔라피 문자 발송

더미(Streamlit 안에서만 동작)로 화면 흐름과 규칙을 확인했다. 이 문서는 더미를 정식 기능으로 바꾸는 기준이다.

## 0. 더미에서 확인된 것 / 확인되지 않은 것

| 구분 | 내용 |
|---|---|
| 확인됨 | 스캔 → 승인 → 로그인 상태에 따른 화면 전환, 3분 만료, 일회용 토큰, 로그인 후 룰렛 1회 추가 |
| 확인됨 | SMS/LMS 구분, 광고 문구 자동 추가, 월 한도 차단, 야간 차단, 수신 동의·수신거부 필터, 발송 내역 |
| 확인 안 됨 | 실제 휴대폰 스캔, 카카오 로그인, 서버↔태블릿 실시간 연결(WebSocket), 실제 문자 수신 |
| 알려진 한계 | user/admin 앱은 별도 프로세스라 데이터를 공유하지 않음 → 백엔드/DB로 해결 |

## 1. QR 로그인

### 흐름
```
태블릿 ──POST /api/auth/qr──────────────▶ 서버: 일회용 토큰 발급(만료 180초)
태블릿 ◀─{token, qr_url, expires_in}────
태블릿 ──WS /api/auth/ws/{token}────────▶ 서버: 연결 유지, 이벤트 대기
휴대폰: QR 스캔 → GET {qr_url} ─────────▶ 서버: scanned 로 변경 → 카카오 인증 페이지로 302
휴대폰: 카카오 로그인 → /api/auth/kakao/callback?code&state
                                         서버: 토큰 교환 → 회원 조회/생성 → logged_in
태블릿 ◀─WS {"event":"logged_in","member":{...},"access_token":"..."}
```

### API 계약 (✅ 구현됨: `backend/app/routers/auth.py`, 테스트 `backend/tests/test_auth.py`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/auth/qr` | body `{table_no}` → `{token, secret, qr_url, expires_in}` |
| GET | `/api/auth/qr/{secret}` | WS 대체 폴링 → `{status}`. 로그인 완료 시 결과(JWT)를 **한 번만** 반환 |
| GET | `/api/auth/kakao/start?token=` | QR 주소. 스캔 처리 후 카카오(키 없으면 모의 화면)로 302. 만료·사용된 QR은 410 |
| GET | `/api/auth/kakao/callback` | 카카오 콜백. 회원 가입/갱신, JWT 발급, 태블릿에 알림 |
| WS | `/api/auth/ws/{secret}` | 이벤트 `status` → `scanned` → `logged_in`(member, access_token) 또는 `expired` |
| GET | `/api/members/me` | JWT 필요. 내 정보 조회 (휴대폰·성별·출생연도는 카카오 로그인 때 자동 수집, 마케팅 수신 동의는 로그인 직전 휴대폰 화면에서 선택) |

- **token / secret 분리**: QR에는 `token`만 들어간다. 로그인 결과는 태블릿만 아는 `secret`으로만 받을 수 있어, QR을 찍은 제3자가 결과를 가로챌 수 없다.
- **모의 모드**: `KAKAO_REST_API_KEY` 가 비어 있으면 `/api/auth/kakao/mock` 의 간단한 로그인 화면을 쓴다. 키를 넣으면 자동으로 실제 카카오 호출로 바뀌고 모의 화면은 404가 된다.
- 운영 전 `JWT_SECRET` 을 반드시 바꿀 것 (기본값 `change-me`).

### 규칙 (더미에서 검증한 것을 그대로 이식)
- 상태 전이: `waiting → scanned → logged_in`, 또는 `expired`. 되돌리기 없음.
- 토큰은 일회용. 승인된 토큰·만료된 토큰은 재사용 불가 (`user/login_demo.py` 와 `user/test_login.py` 가 기준 명세).
- `state` 파라미터로 CSRF 방지: 콜백의 state 가 발급한 토큰과 일치해야 함.
- 로그인 완료 시 JWT 발급, 태블릿 세션에 저장. 만료·로그아웃 정책은 별도 정의.

### 더미에서 교체할 지점
| 더미 | 정식 |
|---|---|
| `user/login_demo.py` (메모리 상태) | `backend/app/stores/login_sessions.py` (+ 이후 Redis 교체 가능한 인터페이스) |
| `login_action("scan"/"approve")` 버튼 | 휴대폰이 부르는 `/kakao/start`, `/kakao/callback` |
| `login_demo_panel` 2초 폴링 fragment | WebSocket 수신 (Streamlit은 폴링 유지 + 서버 WS 병행 권장) |
| `qr_png()` 가짜 QR | `qrcode` 라이브러리로 `qr_url` 인코딩 |
| 고정 닉네임 `카카오` | 카카오 프로필(닉네임) |

### 회원 테이블 `members`
`id, kakao_id(unique), nickname, phone, gender, birthday, mbti, marketing_consent(bool), marketing_consent_at, opted_out(bool), visit_count, last_visit_at, created_at`

## 2. 문자 발송 (솔라피)

### API 계약
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/admin/api/marketing/sms/preview` | body `{grades[], body, send_at?}` → `{type, bytes, targets, remaining, problems[]}` |
| POST | `/admin/api/marketing/sms/send` | preview 와 동일한 검사 후 발송. 응답 `{request_id, count}` |
| GET | `/admin/api/marketing/sms/usage` | 이번 달 SMS/LMS 사용량·한도 |
| GET | `/admin/api/marketing/sms/logs` | 발송 내역 |
| POST | `/api/members/me/opt-out` | 수신거부 (손님/링크 용) |

### 규칙
- 90바이트 이하 SMS, 초과 LMS (한글 2바이트).
- 본문 앞 `(광고)업체명`, 끝 무료수신거부 안내 자동 삽입.
- 수신 동의 + 수신거부 아님인 회원만. 야간(21~08시) 차단. 월 한도 초과 시 차단.
- 한도 값은 설정(`SMS_MONTHLY_LIMIT`, `LMS_MONTHLY_LIMIT`)으로 이동 — 더미의 50/10은 가정값.
- `SMS_DRY_RUN=true` 이면 솔라피를 호출하지 않고 로그만 기록 (실제 키 없이 전체 흐름 테스트 가능).

### 솔라피 호출
- `POST https://api.solapi.com/messages/v4/send-many/detail` (HMAC-SHA256 인증 헤더), 예약은 `scheduledDate`, 예약 취소는 `DELETE /messages/v4/groups/{groupId}/schedule`.

### 테이블
`sms_logs(id, request_id, type, content, target_count, status, error, created_at)`, 월 사용량은 `sms_logs` 집계.

## 3. 진행 현황 (갱신: 2026-10-12)

범례: ✅ 완료 · ⏳ 남음(Claude가 구현) · 🙋 당신이 해야 함

### 3-1. QR 로그인
- ✅ 로그인 세션 저장소 (일회용, 3분 만료, token/secret 분리), `/api/auth/*` REST + `WS /api/auth/ws/{secret}` + 폴링
- ✅ 카카오 클라이언트 (키 없으면 모의 모드, 키 있으면 실제 호출 코드), 회원 저장소(SQLite), JWT, `/api/members/me`
- ✅ **[user] 서버 연동**: 실제 QR 이미지(`qrcode`), 2초 폴링으로 로그인 감지, 만료 시 QR 새로고침, `?table=번호`로 테이블 지정
- ✅ **[user] 로그인 후 화면**: 닉네임 표시, 룰렛 한 번 더, 회원 정보 입력 폼은 제거 (성별·생일·번호는 카카오 로그인 때 자동 수집, 마케팅 수신 동의는 휴대폰 로그인 화면에서 선택)
- ✅ **룰렛 화면 흐름**: 비로그인 START → 로그인 팝업(QR), 로그인 후 START → 룰렛, 이미 돌린 뒤 START → 다른 회원 로그인 팝업(회원당 1회), 비회원 주문/회원 주문 버튼, 로그인한 회원이 하단에 누적 표시 (화면만, 서버 저장 없음)
- ✅ 더미 시뮬레이션(`login_demo.py`) 제거. 서버가 없으면 QR 로그인만 꺼지고 주문 화면은 그대로 동작
- ✅ 테스트: 백엔드 `backend/tests/test_auth.py`, 통합 `tests/test_qr_login_e2e.py`, 실제 서버 두 개 + 브라우저에서 화면의 QR을 디코딩해 스캔을 흉내 내는 확인까지 완료
- ✅ 운영 모드(`APP_ENV=prod`)에서 기본 비밀값(`change-me`)이면 서버 기동 차단
- ⏳ [백엔드] 로그인 세션 Redis 교체 (여러 프로세스로 운영할 때만 필요)
- ⏳ [백엔드] 로그아웃/JWT 만료 정책 정의
- ⏳ 휴대폰 번호를 직접 입력 대신 카카오 수집으로 바꾸려면 비즈 앱 심사 후 `kakao.py` 수정

### 3-2. 문자 발송 (솔라피)
- ✅ 발송 규칙: SMS/LMS 분기, `(광고)` 표기·수신거부 문구 자동 추가, 월 한도, 야간 차단, 수신 동의·번호·수신거부 필터 (`backend/app/services/sms.py`)
- ✅ 솔라피 호출: send-many/detail, 예약 발송·취소, 실패 시 `failed` 로그. `SMS_DRY_RUN=true`(기본)이면 호출 없이 기록만
- ✅ 발송 로그 `sms_logs`와 월 사용량 집계 (실패는 한도에서 제외)
- ✅ API: `/admin/api/marketing/sms/{preview,send,usage,logs}`, `/admin/api/members/{id}/opt-out`, `/api/members/me/opt-out`
- ✅ **[admin] 마케팅 화면 API 연동** (관리자 토큰 로그인, 사용량·미리보기·발송·수신거부·내역).
- ✅ 테스트: `backend/tests/test_sms.py`(솔라피 호출은 MockTransport), 통합 `tests/test_sms_admin_e2e.py`

### 3-2b. AI 질문 (회의록 2.4) — 더미 데이터 화면
- ✅ 메뉴 화면 왼쪽 위 **[💬 AI 질문]** 버튼 → 한 화면에 질문 하나, 큰 선택 카드, 선택하면 바로 다음 질문 (진행 바·이전·닫기)
- ✅ 질문 8개: 배고픔 → 스트레스 → 인원수 → 성비 → 원하는 종류 → 맵기 → 방문 의도 → 예산 (`user/ai_quiz_data.py`, 더미)
- ✅ 결과: 답변 요약, 자동 반영(시간대·날씨), 추천 조합 최대 3개 + 이유 + 담기. 날씨는 더미(`?weather=rain` 등으로 바꿔 보기)
- ✅ 추천 로직 확장: 맵기 필터 오류 수정, 종류·방문 의도·성비·배고픔·스트레스·시간대·날씨 반영, 사장님 가중치 입력 자리(`weight`), 세트 불가·삭제·품절 메뉴 제외
- ⏳ 질문 목록·선택지를 서버/관리자 설정으로 옮기기 (노출 조건 정의 필요), 날씨 API 연동, 회원 정보(MBTI·선호 등)로 일부 질문 건너뛰기
- ⏳ 추천 노출·선택 기록(적중률 계산)과 백엔드 연결, 주종 질문 추가 여부 결정 (지금은 맥주 고정)

### 3-2c. 프론트 데이터 소스 전환 구조 (더미 ↔ API)
- ✅ `DATA_SOURCE=dummy|api|auto` 한 값으로 전환. 화면은 저장소(`user_repository.py`, `admin_repository.py`)만 사용
- ✅ 더미 데이터를 서버 응답과 같은 JSON 모양으로 정리 → 변환 코드 없음. admin 은 더미가 "가짜 서버"(`DummyBackend`)
- ✅ 백엔드: `GET /api/content`(카테고리·룰렛·직원호출·AI 질문·날씨·추천 규칙), `PUT /admin/api/content/{이름}`, 시드는 더미에서 생성(`tools/export_dummy_seed.py`)
- ✅ 연결됨(서버 모드): 메뉴·가격·품절·가중치, 주문 저장, 직원 호출 저장, 추천 노출 기록, 대시보드 통계, 고객 등급, 주문 이력, 메뉴 편집 저장
- ✅ 계약 테스트: 더미와 서버의 JSON 모양이 어긋나면 실패 (`tests/test_admin_data_source.py`, `backend/tests/test_shop_admin.py`)
- ⏳ 서버가 아직 안 주는 것: 날씨 실시간 값(지금은 시드의 고정값), 메뉴 옵션, 관리자 화면에서 콘텐츠(질문·룰렛 등) 편집 UI
- ⏳ 관리자 더미 모드의 마케팅(문자 발송)은 서버가 필요해서 안내만 표시

### 3-2d. 관리자 메뉴 관리 화면 (카테고리 CRUD + 메뉴 등록)
- ✅ 왼쪽 패널: 카테고리 목록(아이콘·이름·메뉴 수, 클릭해서 선택) + 추가 / 수정(이름·아이콘·색상) / 삭제
- ✅ 카테고리를 클릭하면 오른쪽에 그 카테고리의 **메뉴 등록 폼**과 등록된 메뉴 표(수정·행 추가·삭제·저장)가 나온다. 클릭 전에는 안내 문구와 카테고리별 메뉴 수 차트
- ✅ 규칙: 이름 비어 있음·중복 불가, 메뉴가 남은 카테고리는 삭제 불가, 손님 화면용 가상 카테고리(AI 추천 조합·인기메뉴)는 건드리지 않음
- ✅ 더미/서버 모드 모두 동작 (서버 모드는 기존 `PUT /admin/api/content/categories` 로 목록을 통째로 저장, 손님 화면이 10초 안에 반영)
- ⏳ 카테고리 순서 바꾸기, 삭제 전에 메뉴를 다른 카테고리로 한 번에 옮기기, 이미지 파일 업로드(지금은 URL 입력)

### 3-3. 앞서 분석에서 나온 user 페이지 수정 사항 (아직 미수정)
- ✅ 맵기 필터 오류 수정 ("맵지 않게"인데 "매콤한 골뱅이 한 상"이 추천되던 문제)
- ⏳ `requirements.txt`의 streamlit 최소 버전을 1.65로 상향
- ⏳ `.streamlit/config.toml`을 저장소 루트에서 실행해도 적용되게 이동 (user·admin 공통)
- ⏳ 주문 시각 시간대를 한국(Asia/Seoul)으로
- ✅ 지점명 홍대점 반영 (`user/menu_data.py`, 백엔드 `STORE_BRANCH`)
- ⏳ 메뉴·주문·직원 호출을 백엔드 API와 연결 (`shared/api.py` 사용), 관리자와 데이터 공유
- ⏳ 추천에 사장님 가중치·날씨·시간대 반영, 추천 노출/적중 기록
- ⏳ HTML 이스케이프 일관화

## 4. 당신이 해야 할 일 🙋

### 지금 정하면 되는 것
- [x] 지점명: **홍대점**으로 확정, 반영 완료
- [ ] 휴대폰 번호: 카카오 비즈 앱 심사로 받을지, 직접 입력으로 갈지 (현재 코드는 직접 입력 기준)

### 카카오 (로그인 실기기 검증 전까지)
- [ ] developers.kakao.com 앱 생성, REST API 키 발급
- [ ] 카카오 로그인 활성화, Redirect URI 등록 (`{PUBLIC_BASE_URL}/api/auth/kakao/callback`, 개발·운영 각각)
- [ ] 동의항목 설정 (이름·성별·생일·출생연도). 휴대폰 번호는 비즈 앱 심사가 필요함
- [ ] 휴대폰이 접속할 수 있는 서버 주소 확보 (같은 와이파이의 PC 주소, 또는 도메인+HTTPS/터널) → `PUBLIC_BASE_URL`
- [ ] 키를 `backend/.env`에만 입력 (저장소·채팅에 올리지 말 것)

### 카카오 QR 로그인 + Supabase Auth 연동 — 단계별 가이드 🙋

> 목표: 휴대폰이 QR을 스캔하면 **카카오 로그인은 Supabase Auth가 처리**하고, 로그인 결과(회원)를 태블릿에 전달한다.
> 현재 코드는 백엔드가 카카오를 직접 호출한다(`backend/app/services/kakao.py`). 아래 1~7단계는 **당신이 콘솔에서 하는 일**이고,
> 8단계 이후 코드 전환(백엔드가 Supabase로 로그인 처리, `members`를 Supabase 사용자와 연결)은 키가 준비되면 내가 한다.
> 화면 이름은 콘솔 개편으로 조금 다를 수 있으니, 메뉴명이 안 보이면 비슷한 이름을 찾아 진행한다.

**1단계. Supabase 프로젝트 만들기**
1. https://supabase.com 가입 → New project (Region은 `Northeast Asia (Seoul)` 권장, DB 비밀번호는 따로 안전하게 보관).
2. 프로젝트가 만들어지면 **Project Settings → API**(또는 Data API) 에서 아래 값을 메모한다.
   - `Project URL` (예: `https://abcd1234.supabase.co`) → `SUPABASE_URL`
   - `anon` / publishable key → `SUPABASE_ANON_KEY` (공개돼도 되는 키)
   - `service_role` / secret key → `SUPABASE_SERVICE_ROLE_KEY` (**절대 공개 금지**, 서버 `.env`에만)
3. `Project URL`의 `abcd1234` 부분이 **project ref**다. 아래 콜백 주소에 쓰인다.

**2단계. 카카오 개발자 앱 만들기**
1. https://developers.kakao.com 로그인 → **내 애플리케이션 → 애플리케이션 추가하기** (앱 이름 예: `역전할머니맥주 홍대점`).
2. **앱 설정 → 앱 키** 에서 **REST API 키**를 메모한다 (Supabase의 *Client ID* 가 된다).

**3단계. 카카오 로그인 켜기 + Redirect URI 등록 (가장 많이 틀리는 곳)**
1. **제품 설정 → 카카오 로그인** → 활성화 **ON**.
2. **Redirect URI** 에 아래를 **정확히** 등록한다 (끝 슬래시·http/https까지 일치해야 함).
   ```
   https://<프로젝트ref>.supabase.co/auth/v1/callback
   ```
   - 카카오가 돌려보내는 곳은 우리 서버가 아니라 **Supabase**다. 기존 계획의 `{PUBLIC_BASE_URL}/api/auth/kakao/callback` 은 Supabase 방식에서는 카카오에 등록하지 않는다.
3. **보안 → Client Secret** 에서 코드를 생성하고 **활성화 상태: 사용함** 으로 바꾼다 → 코드 값을 메모 (Supabase의 *Client Secret* 이 된다).

**4단계. 카카오 동의항목 설정**
1. **제품 설정 → 카카오 로그인 → 동의항목**.
2. **이름(name)** 을 *필수 동의* 로 설정한다. 로그인한 회원의 표시 이름(`members.nickname`)으로 쓰며, 이름이 없으면 프로필 닉네임(`profile_nickname`)을 대신 쓴다. Supabase 연동은 기본으로 닉네임도 요청하므로 닉네임 동의항목도 켜 두는 것이 안전하다.
3. **카카오계정(이메일)**: Supabase 카카오 연동은 기본적으로 이메일을 요청한다. 이메일은 **비즈 앱 전환(사업자 정보 등록) 후에만** 필수로 받을 수 있다.
   - 비즈 앱이 아직 없다면: Supabase 쪽 카카오 설정에 이메일 없이 로그인을 허용하는 옵션(예: *Allow users without an email*)이 있는지 5단계에서 확인하고 켠다. 켜지 못하면 로그인 시 `KOE205`(잘못된 scope) 오류가 난다 → 그때는 **앱 설정 → 비즈니스 → 비즈 앱 전환** 을 먼저 진행한다.
4. 성별·생일은 선택 동의로 설정해도 되지만, 심사 없이 받을 수 있는 범위인지 화면의 안내를 확인한다. 휴대폰 번호(`phone_number`)는 비즈 앱 심사가 필요하다. 코드는 `KAKAO_SCOPES` 기본값으로 성별·생일·출생연도·휴대폰 번호를 요청하므로, 콘솔에 동의항목을 설정하거나(휴대폰 번호는 심사 후) 설정하지 못한 항목은 `KAKAO_SCOPES` 에서 뺀다. 번호를 못 받으면 해당 회원에게는 광고 문자를 보낼 수 없다.

**5단계. Supabase에 카카오 등록**
1. Supabase 대시보드 → **Authentication → Sign In / Providers**(또는 Providers) → **Kakao** → Enable.
2. **Client ID** = 카카오 *REST API 키*, **Client Secret** = 3단계에서 만든 *Client Secret 코드* 입력 → Save.
3. 같은 화면에 보이는 **Callback URL** 이 3단계에서 카카오에 등록한 주소와 **글자 하나까지 같은지** 비교한다.

**6단계. Supabase에 우리 서버 주소 허용**
1. **Authentication → URL Configuration**.
2. **Site URL**: 운영 주소(예: `https://order.example.com`). 개발 중에는 `http://localhost:8000`.
3. **Redirect URLs** 에 로그인 후 돌아올 우리 백엔드 주소를 추가한다 (개발·운영 각각).
   ```
   http://localhost:8000/**
   http://<서버PC 와이파이 IP>:8000/**
   https://<운영 도메인>/**
   ```
   - 여기에 없는 주소로는 Supabase가 돌려보내 주지 않는다(로그인 후 엉뚱한 Site URL로 가는 증상의 원인).

**7단계. 키를 `.env`에 넣기 (저장소·채팅에 올리지 말 것)**
`backend/.env` 에 아래 값을 추가한다 (예시는 `backend/.env.example` 에 내가 추가해 둔다).
```
SUPABASE_URL=https://<프로젝트ref>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...        # 서버 전용
PUBLIC_BASE_URL=http://<서버PC 와이파이 IP>:8000   # 휴대폰이 접속 가능한 주소
JWT_SECRET=<긴 랜덤 문자열>          # change-me 그대로 두지 말 것
```
- 카카오 키(`KAKAO_REST_API_KEY` 등)는 Supabase 방식에서는 **Supabase 대시보드에만** 넣고 `.env`에는 필요 없다.

**8단계. 코드 연동 (✅ 완료: `backend/app/services/supabase_auth.py`, `routers/auth.py`)**
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` 가 `.env`에 있으면 자동으로 Supabase 방식이 켜진다. 없으면 기존 방식(카카오 직접 / 모의)이 그대로 동작한다.
- 흐름: QR 스캔 → `/kakao/start` 가 PKCE 값을 만들고 Supabase `/auth/v1/authorize?provider=kakao` 로 302 → 카카오 로그인 → Supabase 가 `{PUBLIC_BASE_URL}/api/auth/supabase/callback/{QR토큰}?code=` 로 복귀 → 서버가 code + code_verifier 로 사용자 확인 → 회원 저장, JWT 발급, 태블릿 전환.
- **6단계 Redirect URLs 에 `{PUBLIC_BASE_URL}/**` 가 꼭 있어야 한다** (콜백이 이 경로 아래).
- `members.kakao_id` 에는 `sb:<Supabase 사용자 id>` 가 저장된다. Supabase 방식에서는 모의 로그인 화면이 꺼진다.
- 테스트: `backend/tests/test_auth.py` (Supabase 호출은 가짜 응답, 실제 Supabase 와의 통신은 9단계 실기기 확인에서 검증).

**9단계. 실기기 확인**
1. 서버 실행 후 태블릿 화면의 QR을 **휴대폰 카메라**로 스캔 (휴대폰과 서버가 같은 와이파이, 또는 HTTPS 도메인/터널).
2. 카카오 로그인 화면 → 동의 → 태블릿 화면이 자동 전환되는지 확인.
3. Supabase 대시보드 **Authentication → Users** 에 방금 로그인한 사용자가 생겼는지 확인.
4. 5장 체크리스트(QR 만료, 같은 QR 재스캔 거부)를 수행.

**막혔을 때 자주 나오는 오류**
| 증상 | 원인 / 조치 |
|---|---|
| `KOE006` / `redirect_uri mismatch` | 카카오에 등록한 Redirect URI가 Supabase Callback URL과 다름 (3단계) |
| `KOE205` | 요청한 동의항목(이메일 등)이 카카오 앱에 설정되지 않음 (4단계) |
| `KOE101` / invalid client | REST API 키 오타, 또는 카카오 로그인 활성화 OFF |
| 로그인 후 엉뚱한 주소로 이동 | Supabase *Redirect URLs* 에 우리 주소가 없음 (6단계) |
| 휴대폰에서 QR 주소가 열리지 않음 | `PUBLIC_BASE_URL` 이 `localhost` 로 되어 있음, 또는 다른 와이파이 |
| 개발(HTTP)은 되는데 운영에서 실패 | 운영 도메인용 Redirect URL·카카오 앱 도메인 설정 누락 |

### 솔라피 (실제 발송 전까지)
- [ ] 솔라피 가입, API Key·Secret 발급 → `.env`
- [ ] 발신번호 등록·인증
- [ ] 무료수신거부 번호 방식 확인 → `SMS_OPT_OUT_NUMBER`
- [ ] 현재 무료 제공량·요금 확인 (한도 값 `SMS_MONTHLY_LIMIT`, `LMS_MONTHLY_LIMIT` 조정)

### 법무·정책
- [ ] 개인정보 처리방침, 이용약관
- [ ] 마케팅 수신 동의 문구 (야간 발송 동의 포함)
- [ ] 고객 등급 분류 기준 확정 (현재는 방문 2회/5회/60일의 임시값), AI 추천 적중률 계산 기준 확정

## 5. 실기기 검증 체크리스트 (더미로는 검증 불가) 🙋
- [ ] 휴대폰 카메라로 태블릿 QR 스캔 → (모의 또는 실제) 카카오 로그인 → 태블릿 화면 자동 전환
- [ ] 로그인 중 QR 만료, 같은 QR 재스캔 시 거부
- [ ] 실제 카카오 계정으로 로그인, 닉네임이 화면에 표시
- [ ] 본인 번호로 SMS·LMS 수신, `(광고)` 표기·수신거부 안내 확인
- [ ] 수신거부 후 재발송 시 제외
- [ ] 월 한도 도달 시 차단

## 6. 다음 순서
1. 🙋 같은 와이파이 휴대폰으로 **모의 모드** 실기기 확인 (`PUBLIC_BASE_URL=http://서버PC주소:8000`, README 참고)
2. 🙋 카카오·솔라피 키 준비 → `.env`에 입력 → 실제 모드 전환 후 5장 체크리스트 수행 (솔라피는 `SMS_DRY_RUN=false` 로 바꾸기 전에 본인 번호 1건부터)
3. ⏳ 3-3의 user 페이지 수정 사항 (요청 시)
