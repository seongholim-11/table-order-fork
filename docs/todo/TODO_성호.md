# 성호 TODO · QR 로그인 · 문자 발송 · 관리자 로그인 · 관리자 AI 챗봇

## 시작 전 공통 규칙

| 항목 | 내용 |
|---|---|
| 경로 표기 | `B/`=`backend/app/` · `A/`=`admin/` · `U/`=`user/` · `T/`=루트 `tests/` · `BT/`=`backend/tests/` |
| 브랜치 | 본 리포를 포크 → 내 포크 `main`에서 계속 개발 → PR은 본 리포 `dev`로만(한 PR에 TODO 항목 하나). 시작 전 `git fetch upstream && git pull --rebase upstream dev`. 커밋·PR 메시지 규칙은 `AGENTS.md` |
| 더미 주석처리 (더미 기능만, 구현보다 먼저) | ① 라우터의 `return dummy.xxx(...)` 줄을 `#`으로 주석처리하고 그 아래에 `raise NotImplementedError`를 둔다 ② `B/dummy/` 안의 본인 담당 `*_data.py`(예: `menu_data.py`)에서 해당 함수와 그 파일의 `ENDPOINTS` 줄을 **같이** 주석처리한다(한쪽만 하면 `test_every_listed_dummy_function_exists`가 실패. `dummy/__init__.py`는 고치지 않는다) ③ 구현·테스트가 끝나면 주석처리해 둔 줄을 지운다 |
| 건드리지 않는 것 | 화면쪽 더미(`U/menu_data.py`, `A/admin_dummy_data.py`)는 서버 없이도 화면이 뜨게 하는 대체 데이터라 지우지 않는다 |
| SQL 위치 | SQL은 `B/stores/`에서만 쓴다. 라우터에는 쓰지 않는다. 테이블 정의 기준은 `docs/db/fbgrowth_schema.sql` |
| 테스트 | 서버 `cd backend && uv run pytest -q` · 화면+통합 `python -m pytest tests -q`. 둘 다 실패 없이 통과해야 PR을 보낸다. 테스트를 skip·삭제해서 통과시키지 않는다(더미 교체 시 `skip` 제거만 허용) |
| 새 테스트 | 공용 파일을 건드리지 말고 본인 이름의 새 파일(예: `BT/test_roulette.py`)에 만든다. `BT/test_dummy_get.py`에서는 본인 기능 줄만 뺀다 |
| 코드 작성 | 수정 파일은 최소로, 기존 코드는 최대한 유지, 새 코드에는 초급 개발자도 읽을 수 있는 한국어 주석(무엇을·왜)을 단다 |
| PR 본문 | 변경 내용 · 테스트 방법 · 테스트 결과 · 미해결 문제(없으면 "없음") |

## 진행 순서

| 순서 | 할 일 | 상태 | 비고 |
|---|---|---|---|
| 0 | 0. 개발 흐름 확인 (테스트 버튼) | `POST /api/dev/db-test` (개발 전용) | 확인 전 |
| 1 | 1. QR 로그인 · 2. 문자 발송 점검 | 구현됨 | 새 코드 없이 동작 확인만 |
| 2 | 3. AI 문자 후보 · 외부 정보(날씨·행사) | 완료 | 날씨는 `B/services/external_info.py`(Open-Meteo)에서 직접 가져옴. 재현의 `weather.py`가 생기면 그쪽으로 바꿀 수 있음 |
| 3 | 4. AI 챗봇 | 미구현 | 수용의 `B/services/stats.py`를 호출해 매출을 답함 |
| 4 | 5. 관리자 로그인 | 미구현 | **모든 개발이 끝난 뒤 마지막에** (AGENTS.md 규칙) |
| 선작업 | `B/dummy/`·`B/routers/` 분리 PR | 완료(PR 머지 후 시작) | `dummy.py`는 `B/dummy/*_data.py`로, `user.py`는 기능별 라우터로 나뉨. 마케팅 화면(`marketing*.py`)과 `admin_repository.py` 분리는 하지 않음 |

---

## 0. 개발 흐름 확인 (테스트 버튼) — 가장 먼저

본격적으로 구현하기 전에, 내 PC에서 **포크 → DB 쓰기·읽기 → 커밋·푸시 → PR** 흐름이 막힘없이 되는지 한 번 확인한다. AI에게 아래 내용을 그대로 시키면 된다.

- [ ] **0-1. 포크·최신화**: 본 리포를 포크해 내려받고, `upstream`을 등록한 뒤 `git pull --rebase upstream dev`로 내 `main`을 최신 `dev`에 맞춘다.
- [ ] **0-2. test 테이블 확인**: Supabase `table-order`에는 `test` 테이블(`id`, `value`, `created_at`, RLS 켜짐)을 **이미 만들어 두었다**. 없다면(다른 프로젝트·새 DB) `docs/db/fbgrowth_test_table.sql`을 SQL Editor에서 실행한다.
- [ ] **0-3. 테스트 버튼 만들기** (내 포크에서만, 본 리포에는 올리지 않는다. `DEV_TEST_BUTTON=1`일 때만 보이는 **개발 전용** 버튼):
  - 위치: **손님 시작 화면(룰렛이 있는 화면)**(`U/views/splash.py`)의 "📱 로그인" 버튼(`key="login_open"`) 옆. 화면 코드는 `api`를 직접 부르지 말고 `U/user_repository.py`를 통해서만 서버를 부른다.
  - 서버: `POST /api/dev/db-test`(`B/routers/dev.py` 신규, SQL은 `B/stores/`의 신규 저장소에). `test` 테이블에 임의 값을 INSERT → 같은 행을 다시 SELECT → 값이 같으면 `{"result": 1}`, 아니면 `{"result": 0}`. 행은 지우지 않고 `test` 테이블에 남겨 둔다(Supabase에서 값이 실제로 들어갔는지 눈으로 볼 수 있다).
  - 서버 `.env`에 `DEV_TEST_BUTTON=true`일 때만 이 경로를 열고, 꺼져 있으면 404. 화면 쪽은 환경변수 `DEV_TEST_BUTTON=1`일 때만 버튼을 보인다. `.env.example`에도 적는다.
  - 화면에는 결과 `1`(정상) 또는 실패 이유를 표시한다.
- [ ] **0-4. 테스트**: `cd backend && uv run pytest -q`와 `python -m pytest tests -q`가 통과하는지 확인한다.
- [ ] **0-5. 버튼 확인**: 서버와 손님 화면(`streamlit run user/app.py`)을 `DEV_TEST_BUTTON`을 켠 채 실행하고, 버튼을 눌러 `1`이 나오는지 본다.
- [ ] **0-6. 커밋·푸시·PR**: `AGENTS.md`의 커밋 메시지 규칙대로 커밋하고 내 포크 `main`에 푸시한 뒤, **본 리포 `dev`로 PR**을 보낸다(제목 `종류: 한글 요약`, 본문: 변경 내용·테스트 방법·테스트 결과·미해결 문제).
- [ ] **0-7. 마무리**: 이 PR은 흐름 확인용이므로 **머지하지 않고 PR만 닫는다**(버튼 코드는 `dev`에 들어가지 않는다). 확인이 끝나면 위 항목을 모두 `[x]`로 바꾸고 맨 위 진행 순서 표의 0번 상태를 "완료"로 고친다. 이 체크 변경은 첫 실제 기능 PR에 함께 넣는다.

> 이 단계에서 막히면(포크·푸시·DB 연결·PR 권한 등) 구현을 시작하지 말고 먼저 팀에 알린다. 실제 문제 기록은 `docs/TODO_충돌_오류.md`에 남긴다.

---

## 1. QR 로그인 (구현됨 · 확인만)

더미 없음. 직접 고칠 코드는 없고, 다른 팀원 작업 때문에 깨지지 않는지 확인하는 역할이다.

**목표**: 손님이 테이블 태블릿의 QR을 폰으로 찍어 카카오 로그인하면 태블릿이 자동으로 로그인 상태가 된다. 로그인할 때마다 방문 횟수가 +1 된다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `cd backend && uv run pytest tests/test_auth.py -q` 와 `python -m pytest tests/test_qr_login_e2e.py -q` | 통과. skip 된 테스트는 사유를 읽고 해당 기능 담당자(재현·수용)가 구현할 때 해제되는지 확인 |
| 수동: 서버 + `streamlit run user/app.py` 후 `?table=12`로 접속 → 📱 로그인 → 카카오 키가 없으면 모의 카카오 화면이 뜬다 | 로그인 후 태블릿에 닉네임과 "남은 룰렛 기회"가 보인다 |
| 같은 회원이 다시 로그인 | `members.visit_count`가 1 늘었는지 확인 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| OAuth 인가 코드 방식 | 앱이 비밀번호를 받지 않고, 카카오가 준 일회용 코드(`code`)를 서버가 토큰·프로필로 바꾼다 |
| PKCE | 코드가 새도 쓰지 못하게 `code_verifier`(서버만 앎)로 짝을 맞추는 보안 장치 (`B/services/supabase_auth.py`) |
| 일회용 QR 세션 + 폴링 | 태블릿은 `secret`으로 1~2초마다 "로그인 끝났나요?"를 묻고, 폰이 끝내면 토큰을 받는다 |
| JWT | 서버가 서명한 로그인 증표. `Authorization: Bearer <토큰>`으로 보내고 서버는 서명만 검증한다 (`B/services/tokens.py`) |

**흐름**
```
손님 UI(📱 로그인 버튼)
 → U/ui/login.py login_dialog → U/state/login.py new_login
 → U/server.py create_qr → POST /api/auth/qr
 → B/routers/auth.py → B/stores/login_sessions.py → DB(login_sessions) 저장 → QR 주소 반환 → 태블릿에 QR 표시
 (폰) QR 스캔 → GET /api/auth/kakao/start → 동의(광고 문자 선택) → 카카오 로그인 → GET /api/auth/kakao/callback
 → B/stores/members.py 회원 생성/조회 + 방문 +1 → DB(members) → B/stores/tablet_logins.py record → DB(table_logins)
 (태블릿) 폴링 GET /api/auth/qr/{secret} → access_token → U/state/login.py finish_login → URL ?t=토큰 저장 → UI "OOO님 로그인 완료"
```

**상세 설명 / TODO**

- [ ] `B/routers/auth.py`가 `coupons.issued_today`, `tablet_logins.record`를 부른다. 재현이 `B/stores/coupons.py`·`B/stores/tablet_logins.py`를 고칠 때 함수 이름·인자가 바뀌지 않게 PR 리뷰에서 확인한다.
- [ ] 방문 횟수 규칙은 "로그인할 때마다 +1" 이다. 같은 날 두 번 로그인해도 +1 인지 테스트가 있는지 확인하고 없으면 `BT/test_auth.py`에 하나 추가한다.
- [ ] `PUBLIC_BASE_URL`은 폰이 접속할 수 있는 주소여야 한다. 같은 와이파이의 서버 PC IP로 바꿔 시연 전에 폰으로 확인한다.

---

## 2. 문자 발송 (구현됨 · 확인만)

더미 없음. 솔라피 연동은 끝났고, 시연 전 점검이 남아 있다.

**목표**: 사장님이 등급·문구를 골라 미리보기 후 즉시 또는 예약으로 광고 문자를 보내고, 기록을 보고, 예약을 취소하고, 수신거부를 등록한다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `uv run pytest backend/tests/test_sms.py -q`, `python -m pytest tests/test_sms_admin_e2e.py -q` | 통과 |
| 수동(`SMS_DRY_RUN=true`) | 관리자 > 마케팅 > AI 문자에서 발송 → 기록에 `dry_run` 으로 남고 실제 문자는 안 나간다 |
| 수동(실발송, 시연 직전 1회) | `SMS_DRY_RUN=false` + 솔라피 키·발신번호·`SMS_OPT_OUT_NUMBER` 설정 후 본인 번호로 1건 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 광고성 문자 법규 | 수신 동의한 사람에게만, 본문 앞에 "(광고)", 끝에 무료수신거부 번호를 붙여야 한다. 서버가 자동으로 붙인다 |
| SMS / LMS | 90바이트 이하는 SMS, 넘으면 LMS(더 비쌈). 월 한도(`SMS_MONTHLY_LIMIT`, `LMS_MONTHLY_LIMIT`)를 넘으면 막는다 |
| dry-run | 외부 서비스를 부르지 않고 기록만 남기는 안전 모드. 개발 중에는 항상 켜 둔다 |
| 예약 발송 | 보낼 시각을 `sms_logs.scheduled_at`에 저장하고 상태를 `scheduled`로 둔다. 취소하면 `canceled` |

**흐름**
```
UI(AI 문자 탭 · 발송 버튼) → A/views/marketing.py → A/admin_repository.py ApiBackend.sms_send
 → POST /admin/api/marketing/sms/send → B/routers/admin/sms.py → B/services/sms.py
   (수신 동의·수신거부 필터, (광고) 문구 붙이기, SMS/LMS 판별, 월 한도 검사)
 → 솔라피 API(dry-run 이면 건너뜀) → B/stores/sms_logs.py → DB(sms_logs, sms_log_recipients)
 → 결과(status, 대상 수) → UI "발송 완료" + 발송 내역 표
```

**상세 설명 / TODO**

- [ ] 시연 전 실발송 1회 점검(위 표). 키·발신번호는 `.env`에만 두고 화면·로그·커밋에 절대 노출하지 않는다.
- [ ] 3번(후보 생성)을 붙일 때 `B/routers/admin/sms.py`의 기존 함수 순서·이름은 바꾸지 않고 아래에 추가만 한다.

---

## 3. AI 문자 후보 · 외부 정보(날씨·행사) (구현됨)

### 3-1. `POST /api/admin/marketing/sms/candidates` · `GET /api/admin/marketing/external-context`

**현재 상태**: 후보 문구를 만드는 코드(`suggest_candidates`)가 서버가 아니라 관리자 화면 쪽 `A/marketing_ai.py`에서 직접 돈다. 날씨·행사는 `external_context()`가 빈 문자열을 돌려줘 고정 문구가 쓰인다. (더미 응답 코드는 없으므로 주석처리할 서버 코드는 없다.)

**목표**: 서버 API 두 개로 옮겨 화면이 `repo.sms_candidates()`, `repo.external_context()`만 부르게 한다. 응답은 현재 `suggest_candidates`와 같은 모양 `[{keywords, grades, body, source("ai"|"template")}]`.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| 새 `BT/test_sms_candidates.py` | AI 키가 없을 때 `source == "template"` 후보 최대 5개, 수신 가능 회원이 없는 등급 조합은 빠짐 |
| 새 테스트(외부 API는 `monkeypatch`로 가짜 응답) | `external-context`가 오늘 날짜 한 줄을 만들고 두 번째 호출은 DB에서 읽는다 |
| 수동 | AI 문자 탭에서 "AI 문구 생성" → 후보 카드가 뜨고 선택하면 본문이 채워진다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 프롬프트 구성 | 시스템 지시 + 매장 데이터 요약 + 키워드를 합쳐 LLM에 보낸다. 데이터에 없는 내용은 만들지 못하게 지시한다 |
| 폴백(대체 경로) | AI 호출이 실패하거나 키가 없으면 템플릿 문구로 대신해 화면이 멈추지 않게 한다 |
| 캐시 | 하루 한 번 바뀌는 날씨·행사는 `external_context(day)`에 저장해 두고 재사용한다 (외부 호출 횟수 절약) |
| 동시 호출 | 후보 5개를 순서대로 부르면 느리니 `ThreadPoolExecutor`로 동시에 부른다 (기존 코드 참고) |

**흐름**
```
UI(AI 문구 생성 버튼) → A/views/marketing.py make_ai_candidates → repo.sms_candidates (새 메서드)
 → POST /admin/api/marketing/sms/candidates → B/routers/admin/sms.py
 → B/services/sms_candidates.py (신규: 회원·주문·메뉴 요약 수집 → 키워드 조합 → 문구 생성)
 → [DB(members, orders, menus) 읽기] + external-context 읽기 → DB(external_context) → LLM(키 없으면 템플릿)
 → 후보 목록 → UI 후보 카드
```

**상세 설명 / TODO**

- [x] `B/services/sms_candidates.py`(신규)에 `A/marketing_ai.py`의 `keyword_combos`, `template_sms`, `generate_sms`, `suggest_candidates` 로직을 서버용으로 옮긴다. 화면쪽 원본은 지우지 말고 둔다(`DATA_SOURCE=dummy` 대체용).
- [x] 회원·주문 요약은 직접 SQL을 쓰지 말고 `B/stores/members.py` 등 기존 store 메서드를 쓴다. 필요한 조회가 없으면 본인이 만든 새 store 파일에 추가한다.
- [x] `B/routers/admin/external.py`(신규): `GET /admin/api/marketing/external-context` → 오늘(KST) 행 조회, 없으면 날씨는 재현의 `B/services/weather.py`로 채워 `external_context`에 저장. 행사 문구는 비워 두고 사장님이 입력하는 방식은 추후 결정.
- [x] 결정(구현은 제미나이로 진행, 팀 확인 필요): 현재 문구 생성은 Anthropic API(`ANTHROPIC_API_KEY`)를 쓰고, 챗봇은 제미나이로 정해져 있다. 문자 후보도 제미나이로 통일할지 결정한다.
- [x] `A/admin_repository.py`의 `ApiBackend`에 `sms_candidates` 메서드를 추가했다(`external_context`는 서버가 후보 생성 때 직접 쓰므로 화면 메서드는 만들지 않음).
- 구현 메모: 행사는 서울시 문화행사 정보 API(`SEOUL_OPENAPI_KEY`, 마포구·오늘 진행 중 최대 2개), 문구 생성은 제미나이(`GEMINI_API_KEY`, 없으면 템플릿). 메뉴·주문 저장소가 아직 뼈대라 인기·가중치 메뉴는 그 저장소가 구현되면 자동 반영된다.

---

## 4. AI 챗봇 (미구현)

### 4-1. `POST·GET /api/admin/marketing/chat/sessions` · `GET·DELETE …/sessions/{sessionId}` · `POST …/sessions/{sessionId}/messages`

**현재 상태**: 대화가 `st.session_state`(브라우저 메모리)에만 있고, 답변은 규칙 기반 가짜 응답(`RuleBasedClient`)이다. 새로고침하면 대화가 사라진다. 더미 서버 코드는 없다.

**목표**: 대화 세션·메시지를 DB에 저장하고, 질문("오늘 매출 얼마야")에 **DB의 실제 데이터**를 근거로 제미나이가 답한다. RAG(문서 검색)는 쓰지 않고 데이터 요약을 프롬프트에 직접 넣는다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| 새 `BT/test_chat.py` (제미나이 호출은 `monkeypatch`로 가짜 응답) | 세션 생성 → 첫 인사 메시지 1개, 질문 전송 → user/assistant 메시지 2개 추가, 목록은 최근순, 삭제하면 메시지도 같이 삭제 |
| 키 없음 | `GEMINI_API_KEY`가 없으면 안내 문구로 답하고 500이 나지 않는다 |
| 수동 | 챗봇 탭에서 질문 → 새로고침 → 대화가 남아 있다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| LLM API 호출 | HTTP로 `프롬프트 + 대화 이력`을 보내면 텍스트가 돌아온다. 호출마다 대화 이력 전체를 다시 보내야 문맥이 유지된다 |
| 컨텍스트 주입(RAG 없음) | 매출·메뉴·고객 요약을 문장으로 만들어 시스템 프롬프트에 붙인다. "아래 데이터에 없는 내용은 모른다고 답하라"를 꼭 넣어 거짓말(환각)을 줄인다 |
| 세션 1 : 메시지 N | `chat_sessions`(대화방) 한 줄에 `chat_messages`(말풍선)가 여러 줄. 세션을 지우면 `on delete cascade`로 메시지도 지워진다 |
| 무료 API 한도 | 분당·일일 호출 제한이 있다. 429가 오면 "잠시 후 다시"로 안내하고 재시도는 하지 않는다 |
| 비밀 키 관리 | `GEMINI_API_KEY`는 `.env`에만 두고 `Settings`로 읽는다. 커밋·로그 노출 금지 |

**흐름**
```
UI(챗봇 탭 · 질문 입력) → A/views/marketing.py marketing_chatbot_tab → repo.chat_send (새 메서드)
 → POST /admin/api/marketing/chat/sessions/{id}/messages → B/routers/admin/chat.py (신규)
 → B/services/chat.py (신규): 대화 이력 읽기 + 매출·메뉴·고객 요약 만들기(수용의 stats 서비스 호출)
 → 제미나이 API → 답변 → B/stores/chat.py (신규): user·assistant 메시지 저장 → DB(chat_sessions, chat_messages)
 → 답변 → UI 말풍선
```

**상세 설명 / TODO**

- [ ] `B/core/settings.py`에 `gemini_api_key`와 `chat_owner_id`(임시 owner uuid) 추가, `backend/.env.example`에 `GEMINI_API_KEY=`, `CHAT_OWNER_ID=` 두 줄 추가.
- [ ] `B/stores/chat.py`(신규): `create_session`, `list_sessions`, `get_session(메시지 포함)`, `add_message`, `delete_session`. 테이블은 `chat_sessions`, `chat_messages`.
- [ ] **임시 owner (결정됨)**: `chat_sessions.owner_id`는 `auth.users`를 참조하는 NOT NULL이고 관리자 인증은 마지막(5번)에 하므로, 개발 중에는 Supabase `auth.users`에 이미 있는 계정 1개의 uuid를 `CHAT_OWNER_ID` 환경변수로 받아 모든 세션의 owner로 쓴다.
  - uuid는 Supabase 대시보드 Authentication > Users에서 복사해 각자 `backend/.env`에만 넣는다(코드·커밋·화면·로그에 쓰지 않는다. DB 스키마는 바꾸지 않는다).
  - `B/stores/chat.py`의 `create_session`이 `settings.chat_owner_id`를 `owner_id`로 넣는다. 값이 비어 있으면 세션 생성은 "CHAT_OWNER_ID 설정이 필요합니다"라는 오류로 돌려주고 500을 내지 않는다.
  - 로컬 SQLite로 개발할 때는 `auth.users` FK가 없으므로 아무 uuid 문자열이어도 동작한다. Supabase에서는 실제 존재하는 uuid여야 한다.
  - `chat_sessions.id`는 uuid라 `SERIAL_TABLES`에 없다. `uuid.uuid4()`로 코드에서 만들어 넣고 그 값을 반환한다(`chat_messages`는 이미 `SERIAL_TABLES`에 들어 있음).
  - 5번(관리자 로그인)을 할 때 `require_admin`이 돌려주는 사용자 id로 교체하고 `CHAT_OWNER_ID`는 제거한다.
- [ ] `B/routers/admin/chat.py`(신규) 5개 엔드포인트. 없는 세션이면 404.
- [ ] `B/services/chat.py`(신규): 오늘 매출 등은 `B/services/stats.py`(수용)의 함수를 **호출만** 한다. 수용이 구현하기 전에는 주문 합계를 직접 간단히 계산하지 말고, 해당 요약 항목은 "아직 집계 전"으로 두고 진행한다.
- [ ] 제미나이 호출은 `httpx`(이미 사용 중)로 하고 타임아웃(15초)과 예외 처리를 넣는다. 실패 시 "답변을 만들지 못했어요" 메시지를 저장하지 말고 오류로 돌려준다.
- [ ] `A/views/marketing.py`의 `marketing_chatbot_tab`만 수정한다(같은 파일의 AI 추천 탭은 석원 담당). `A/admin_repository.py`의 `ApiBackend`에는 `chat_*` 메서드를 본인 구역에 추가.
- [ ] 완료 후: 규칙 기반 `RuleBasedClient`는 `DATA_SOURCE=dummy` 대체용으로 남겨 둔다.

---

## 5. 관리자 로그인 (미구현 · 마지막에 진행)

### 5-1. `GET /api/v1/owner/me`

**현재 상태**: `ADMIN_TOKEN` 하나로 모든 관리자 API를 보호한다 (`B/core/dependencies.py require_admin`). 화면은 `ADMIN_SKIP_TOKEN=1`이면 토큰 입력 없이 자동 로그인한다. 정식 인증은 **모든 기능 개발이 끝난 뒤** Supabase Auth(`owners` 테이블)로 바꾼다.

**목표**: 사장님 계정으로 로그인하면 `owner/me`가 토큰을 검증하고 매장 정보를 돌려준다. 계정이 `owners`에 없으면 403.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| 새 `BT/test_owner_me.py` | 토큰 없음 401, 잘못된 토큰 401, 사장님이 아닌 계정 403, 정상 200 + 매장 정보 |
| 기존 관리자 API 테스트 | `ADMIN_TOKEN` 방식이 남아 있는 동안 기존 테스트가 그대로 통과 |
| 수동 | `ADMIN_SKIP_TOKEN=0`로 관리자 화면을 열어 로그인 화면이 뜨는지, 로그인 후 메뉴가 열리는지 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 인증 vs 인가 | 인증=누구인지 확인(401), 인가=그 사람이 해도 되는지 확인(403) |
| Bearer 토큰 / JWT | 요청 헤더에 증표를 실어 보내고, 서버는 서명으로 위조 여부만 확인한다 |
| Supabase Auth | 가입·로그인·토큰 발급을 대신해 주는 서비스. 사용자는 `auth.users`에 있고, 사장님 여부는 우리 `owners` 테이블로 따로 관리한다 |
| 점진적 교체 | 한꺼번에 바꾸지 말고 `require_admin` 한 곳만 바꾸면 전체 관리자 API가 따라오게 만든다 |

**흐름**
```
UI(관리자 로그인 화면) → A/views/login.py → A/admin_repository.py connect
 → (현재) GET /admin/api/menus 로 토큰 확인 → (변경) GET /api/v1/owner/me
 → B/core/dependencies.py require_admin (Supabase JWT 검증) → B/services/supabase_auth.py
 → DB(owners 에 user_id 있는지) → 매장 정보(B/stores/store_info.py) → UI 메뉴 화면
```

**상세 설명 / TODO**

- [ ] 마지막 단계 전에는 코드를 바꾸지 않는다. 그동안 `ADMIN_TOKEN`은 운영에서 기본값(`change-me`)을 쓰지 않는다(`APP_ENV=prod`이면 서버가 거부한다).
- [ ] 시작할 때: `B/routers/admin/owner.py`(신규), `require_admin`에서 Supabase 토큰 검증 추가, `A/views/login.py`·`connect()` 수정.
- [ ] 챗봇의 임시 `CHAT_OWNER_ID`(4번)를 로그인한 사장님의 id로 교체하고 환경변수를 제거한다.
