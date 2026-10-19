# 석원 TODO · 관리자 AI 추천 · 직원 호출 · 룰렛 설정

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

| 순서 | 할 일 | API | 상태 |
|---|---|---|---|
| 0 | 0. 개발 흐름 확인 (테스트 버튼) | `POST /api/dev/db-test` (개발 전용) | 확인 전 |
| 1 | 1. 직원 호출 (손님 호출 → 관리자 확인) | `POST /api/v1/staff-calls`, `GET /api/v1/staff-call-items`, `GET /admin/api/calls`, `POST /admin/api/calls/{callId}/done` | 완료 |
| 2 | 2. 룰렛 설정 | `GET /api/v1/roulette/prizes`, `PUT /api/v1/owner/roulette/prizes` | 완료 |
| 3 | 3. 관리자 AI 추천 | `GET /api/admin/marketing/opportunities?round=` | 완료 |

**다른 팀원과 겹치는 지점**

| 파일 | 누구와 | 규칙 |
|---|---|---|
| `B/routers/staff_calls.py` | (석원 전담) | `create_call`(`/calls`)이 이 파일에 있다. 새 직원 호출 엔드포인트도 여기에 추가 |
| `B/stores/roulette_prizes.py`(신규) | 재현이 룰렛 추첨에서 `list()`를 호출 | 석원이 만들고 `list()`의 반환 모양을 재현과 먼저 합의 |
| `B/routers/admin/content.py`, `B/seed/content.json` | 서준·재현 | 본인 키(`roulette_prizes`, `staff_calls`)만 옮기고 지운다 |
| `B/dummy/` | 재현·서준·수용 | `call_data.py`의 `call_created`, `content_data.py`의 `content_saved`, 룰렛·직원 호출 관련 줄만 |
| `A/views/marketing.py`, `A/marketing_ai.py` | 성호(AI 문자·챗봇 탭) | 석원은 `marketing_recommend_tab`, `next_rec_round`, `pick_recommendations`, `recommend`만. 성호의 함수는 건드리지 않는다 |
| `A/admin_repository.py` | 모두 | `# ---- 이벤트: 룰렛 ----` 구역과 `ApiBackend`의 룰렛·직원 호출 메서드만 |
| `U/user_repository.py` | 재현·서준 | `_fetch_content`의 `roulette_prizes`·`staff_calls` 줄만 |
| `A/app.py` | 성호 | 관리자에 "직원 호출" 화면을 새로 추가하려면 `PAGES`/`TOP_PAGES`에 한 줄이 필요하다. 그 줄은 PR을 작게 나눠 먼저 올리고 성호에게 알린다 |

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

## 1. 직원 호출 (완료)

손님이 "물·수저 주세요"를 누르면 → 관리자가 목록에서 보고 → 처리 완료를 누르는 한 줄기 흐름이다. 4개 API가 모두 `staff_calls`·`staff_call_items` 두 테이블(`B/stores/shop_calls.py`)을 쓴다.

### 1-1. `GET /api/v1/staff-call-items` (요청 항목 목록)

**목표**: 직원 호출 창에 보이는 항목(💧 물, 🥄 수저 등)을 DB `staff_call_items`에서 읽는다. 지금은 `GET /api/content`의 `staff_calls`(JSON 파일)에서 나온다.

**테스트 방법**: 새 `BT/test_staff_calls.py` — 응답이 `["💧 물", …]` 문자열 목록이고 `sort_order` 순 / 비어 있으면 시드(`content.json`의 `staff_calls`)로 채워짐 / 라벨 중복 불가(unique).

**중요 이론**: 시드(비어 있을 때만 초기값 채우기), 정렬 컬럼(`sort_order`), 라벨 중복 방지(`unique`), 화면이 이미 쓰는 모양(문자열 목록)을 그대로 돌려줘야 화면을 안 고친다.

**흐름**
```
UI(직원 호출 다이얼로그 열기) → U/ui/dialogs.py staff_dialog ← ctx.STAFF_CALLS ← U/user_repository.py load_content
 → GET /api/v1/staff-call-items → B/routers/staff_calls.py(신규) → B/stores/shop_calls.py items()
 → DB(staff_call_items) → ["💧 물", "🥄 수저", …] → UI 체크 항목
```

**상세 설명 / TODO**

- [x] 더미 정리: `B/seed/content.json`의 `staff_calls` 키를 전용 시드와 API로 분리했다. 공용 콘텐츠 저장 더미는 다른 콘텐츠가 사용하므로 유지한다.
- [x] `shop_calls.py`에 호출 항목 목록과 비어 있을 때 전용 시드로 복구하는 로직을 추가했다.
- [x] `U/user_repository.py _fetch_content`에서 `staff_calls`를 새 경로로 받도록 수정했다.

### 1-2. `POST /api/v1/staff-calls` (직원 호출 등록)

**목표**: 손님이 고른 항목들(복수)로 호출을 `staff_calls`에 저장한다. 지금은 저장하지 않는 더미다(`POST /api/calls`).

**테스트 방법**: `BT/test_shop_admin.py::test_orders_calls_and_member_link`의 호출 부분 / 새 테스트 — 항목이 비면 422 / 저장 후 `{id}` / `items`가 목록으로 저장되고 `done_at`은 비어 있음 / 로그인 없이도 호출 가능(비회원 손님도 호출해야 한다).

**중요 이론**: 배열 컬럼 저장(`items`는 DB에서 배열, SQLite 호환 구조에서는 JSON 문자열 → `db.to_list`/`db.from_list`), 요청 검증(`CallIn`: `table_no ≥ 1`, `items ≥ 1개`)은 이미 있다. 인증이 필요 없는 쓰기 API는 악용되기 쉬우므로 같은 테이블의 연속 호출이 너무 잦으면 막는 것을 고려(필수 아님).

**흐름**
```
UI(직원 호출 · 항목 선택 · 호출 버튼) → U/ui/dialogs.py staff_dialog → ctx.REPO.create_call(table, picks)
 → POST /api/calls {table_no, items} → B/routers/staff_calls.py create_call
 → B/stores/shop_calls.py add_call → DB(staff_calls INSERT) → {id}
 → UI "호출했어요" 토스트 + 세션 호출 기록
```

**상세 설명 / TODO**

- [x] 더미 정리: `create_call`의 더미 호출과 `B/dummy/call_data.py`의 직원 호출 더미를 제거했다.
- [x] `shop_calls.py`의 `add_call`, `call`을 구현했다.
- [x] `POST /api/v1/staff-calls`와 기존 호환 경로 `/api/calls`가 같은 DB 저장 로직을 사용한다.

### 1-3. `GET /admin/api/calls`, `POST /admin/api/calls/{callId}/done` (관리자 호출 관리)

**목표**: 관리자가 호출 목록(최신순, 처리 여부)을 보고 "처리 완료"를 누르면 `done_at`을 기록한다. **관리자 화면이 아직 없다**(과거 삭제됨) — 화면 추가도 이 작업에 포함된다.

**테스트 방법**: 새 테스트 — 호출 3건 등록 → 목록이 최신순 / `done` 호출 후 해당 건만 `done=true` / 없는 id는 404 / 이미 처리된 건을 다시 처리해도 오류 없음(멱등) / 인증 없으면 401. 화면: 새 `tests/test_admin_calls_page.py`(AppTest)로 목록이 그려지는지만 확인.

**중요 이론**: 상태를 컬럼 하나로(`done_at` null = 미처리, 값 있음 = 처리됨). 주문 상태(접수/조리중)는 만들지 않는다는 제품 규칙과 구분하자 — **호출 처리 완료**만 허용되고 주문 상태 기능은 없다. 폴링(관리자 화면이 주기적으로 새로고침)이 가장 단순한 실시간 갱신이다.

**흐름**
```
UI(관리자 > 직원 호출 관리 · 처리 완료 버튼) → A/views/calls.py(신규) → repo.calls / repo.call_done (A/admin_repository.py)
 → GET /admin/api/calls · POST /admin/api/calls/{id}/done → B/routers/admin/calls.py(신규)
 → B/stores/shop_calls.py list_calls / mark_done → DB(staff_calls UPDATE done_at)
 → [{id, table_no, items, ts, done}] → UI 호출 카드(미처리 먼저)
```

**상세 설명 / TODO**

- [x] `shop_calls.py`에 `list_calls()`, `mark_done(call_id)`를 추가하고 `B/routers/admin/calls.py`에 관리자 API를 구현했다.
- [x] `A/views/calls.py`, `A/app.py`, Repository와 더미 백엔드가 같은 호출 응답 구조를 사용한다.
- [x] 관리자 직원 호출 화면 상단에 새로고침 버튼을 제공한다.

---

## 2. 룰렛 설정 (더미)

### 2-1. `GET /api/v1/roulette/prizes`, `PUT /api/v1/owner/roulette/prizes`

**현재 상태**: 룰렛 칸 구성은 `/api/content`의 `roulette_prizes`(JSON 파일)에서 나오고, 관리자 저장(`PUT /admin/api/content/roulette_prizes`)은 저장하지 않는 더미다. 검증(칸 2~8개, 가중치 합 0 초과, 색상 형식, 할인율 1~100)은 이미 **화면 쪽**(`A/admin_repository.py save_roulette`)에 있다.

**목표**: 칸 구성·확률 가중치를 `roulette_prizes` 테이블에 저장하고 읽는다. 저장은 목록 통째로 교체(칸 순서 유지). 손님 화면의 룰렛과 재현의 서버 추첨이 같은 데이터를 쓴다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `python -m pytest tests/test_admin_events_page.py -q` | `skip`/`pytest.skip` 중 이 기능 때문인 것(저장 후 조회 반영)을 해제하고 통과 |
| 새 `BT/test_roulette_prizes.py` | 저장 → 조회에 반영 / 칸이 1개 또는 9개면 422 / 가중치 전부 0이면 422 / `kind=discount`인데 `percent` 없음 422 / `kind=free`인데 존재하지 않는 메뉴 id면 422 / 인증 없으면 401(PUT) |
| 응답 모양 | 지금 손님 화면이 받는 `[{label, short, emoji, color, kind, percent|item_id, weight}]`와 같다 |
| 수동 | 관리자 > 이벤트에서 확률 가중치를 바꾸고 저장 → 새로고침해도 유지 → 손님 룰렛에 반영(10초 캐시 이내) |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 확률 가중치 | 칸의 당첨 확률 = 그 칸의 가중치 ÷ 모든 칸 가중치의 합. 합이 0이면 모두 같은 확률 |
| 서버에서도 검증 | 화면 검증은 우회될 수 있다. 같은 규칙을 서버에서도 검사한다 (이중 방어) |
| 통째 교체 | 한 트랜잭션에서 기존 칸을 지우고 새 칸을 넣는다. 중간에 실패하면 이전 구성이 그대로 남아야 한다 |
| 외래 키 | 서비스 칸의 `menu_id`는 서준의 `menus.id`를 참조한다. 없는 메뉴면 DB가 거부한다 |
| 쿠폰은 사본을 갖는다 | 이미 발급된 쿠폰(`coupons.label`)은 칸이 바뀌어도 그대로다. 그래서 칸을 지워도 `prize_id`는 `set null` |
| HTML 문구 | 칸 문구(`label`)에 `<br><b>` 같은 HTML이 들어간다. 사용자 입력은 `escape` 처리 후 저장(화면에서 이미 처리) |

**흐름**
```
UI(관리자 > 이벤트 > 룰렛 · 칸 편집 · 저장) → A/views/events.py → repo.save_roulette (검증·변환)
 → PUT /admin/api/…/roulette/prizes [{label, short, emoji, color, kind, percent|item_id, weight}]
 → B/routers/roulette_prizes.py(신규) (서버 검증) → B/stores/roulette_prizes.py(신규) 통째 교체
 → DB(roulette_prizes, menus 참조) → 저장된 목록
 → (손님) GET /api/v1/roulette/prizes → U/user_repository.py → U/ui/roulette.py 가 같은 칸으로 룰렛을 그림
```

**상세 설명 / TODO**

- [x] `B/stores/roulette_prizes.py`(신규): `list()`(`sort_order` 순, 화면 모양으로 변환: `short_text→short`, `menu_id→item_id`), `replace(prizes)`, 비어 있을 때 전용 시드의 룰렛 설정으로 초기화.
- [x] `B/routers/roulette_prizes.py`(신규): 손님용 `GET /api/v1/roulette/prizes`, 관리자용 `PUT /admin/api/owner/roulette/prizes`(인증 필요). 서버 검증은 `save_roulette`와 같은 규칙.
- [x] 더미 정리: `B/seed/content.json`의 `roulette_prizes` 키를 전용 시드로 옮겼다. 공용 콘텐츠 저장 엔드포인트는 직원 호출·카테고리 이관 뒤 정리한다.
- [x] `A/admin_repository.py`: `ENDPOINTS["roulette"]`와 `ApiBackend.roulette_prizes`/`save_roulette_prizes`의 경로를 새 경로로 변경.
- [x] `U/user_repository.py _fetch_content`의 `roulette_prizes`를 새 경로로 받도록 수정.
- [x] `B/dummy/content_data.py`에서 룰렛 더미를 분리했다. 공용 `content_saved`는 직원 호출·카테고리가 아직 사용하므로 유지한다.

---

## 3. 관리자 AI 추천 (완료)

### 3-1. `GET /api/admin/marketing/opportunities?round=`

**현재 상태**: 서버와 더미 서버가 같은 공통 규칙 엔진으로 DB·시연 데이터를 분석한다. 추천은 4개씩 순환하고, 문자 실행형 카드는 AI 문자 화면에 대상과 초안을 넘긴다. 규칙 기반이며 LLM은 쓰지 않는다.

**목표**: 서버가 DB 데이터로 추천 카드 `[{title, why, action}]`를 만들어 돌려준다. 화면의 "🔄 재추천" 버튼은 `round`를 하나 올려 **다음 4개 묶음**을 받는다(끝까지 가면 처음으로). 현재 규칙(휴면 고객·단골·신규·한가한 시간대·인기 메뉴·안 팔리는 메뉴·품절·AI 적중률·수신 동의)을 그대로 서버로 옮긴다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| 기존 `python -m pytest tests/test_marketing_ai.py -q` | 화면 쪽 규칙 테스트가 그대로 통과(원본은 지우지 않음) |
| 새 `BT/test_opportunities.py` | 데이터가 없으면 "데이터를 더 모아 볼까요?" 카드 1개 / 휴면 회원이 있으면 휴면 카드가 나옴 / `round=0,1,2…`로 묶음이 4개씩 바뀌고 끝에서 처음으로 돌아옴(`round % 묶음 수`) / 카드마다 `title, why, action` 키 / 인증 없으면 401 |
| 수동 | 관리자 > 마케팅 > AI 추천에서 카드가 뜨고 "재추천"을 누르면 다른 카드가 나온다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 규칙 기반 추천 | "조건(휴면 고객이 있다) → 카드(되찾기 제안)"를 `if`로 쌓아 만든다. 같은 데이터면 항상 같은 결과라 테스트하기 쉽다 |
| 근거 있는 문장 | 카드마다 `why`에 **실제 숫자**(휴면 3명, 전체의 25%)를 넣어야 사장님이 믿는다. 숫자는 DB에서 가져온다 |
| 페이지 순환 | `page = round % 전체 묶음 수`. 마지막 묶음이 모자라면 앞에서 채운다(`pick_recommendations` 참고) |
| 읽기 전용 의존 | 이 API는 새 테이블을 만들지 않는다. 회원 등급(수용의 `grades`), 주문·메뉴·AI 적중률(수용의 `stats`), 메뉴 가중치(서준)를 **읽기만** 한다 |
| LLM은 선택 | 규칙 카드는 LLM 없이 충분하다. 문구를 다듬는 용도로 LLM을 붙이는 것은 나중 일이고, 챗봇(성호)과는 별개다 |

**흐름**
```
UI(마케팅 > AI 추천 탭 · 🔄 재추천) → A/views/marketing.py marketing_recommend_tab → next_rec_round(round+1)
 → repo.opportunities(round) (새 메서드, A/admin_repository.py) → GET /admin/api/marketing/opportunities?round=N
 → B/routers/admin/opportunities.py(신규) → B/services/opportunities.py(신규): 맥락 수집 → 규칙 평가 → 카드 목록 → 4개 묶음 선택
 → [DB(members, orders, menus, recommendation_events) 읽기: 각 store 와 수용의 stats 서비스 호출]
 → {items:[{title, why, action}], page, pages} → UI 카드 4개 + "추천 N/M"
```

**상세 설명 / TODO**

- [x] `B/services/opportunities.py`(신규): `A/marketing_ai.py`의 `build_context`·`recommend`·`pick_recommendations`를 서버 용도로 옮긴다. 화면쪽 원본은 `DATA_SOURCE=dummy` 대체용이라 **지우지 않는다**. 로직을 복사할 때 "같은 입력 → 같은 카드"가 되는지 위 테스트로 확인한다.
- [x] 의존 데이터(주문 합계, 적중률 등)는 수용의 `B/services/stats.py dashboard()`를 호출한다. 수용이 끝나기 전에는 그 항목의 카드(AI 적중률 등)를 건너뛰고 TODO 주석을 남긴다(나머지 카드는 동작).
- [x] `B/routers/admin/opportunities.py`(신규, 등록은 성호의 선작업 PR 또는 `B/routers/admin/__init__.py` 한 줄). `round`는 `Query(default=0, ge=0)`.
- [x] 화면: `A/views/marketing.py`의 `marketing_recommend_tab`, `next_rec_round`, `pick_recommendations`만 수정한다. 서버가 닿으면 서버 카드, 아니면 기존 로컬 계산(`DATA_SOURCE=auto`의 폴백).
- [x] `A/admin_repository.py ApiBackend`와 `A/admin_dummy_data.py DummyBackend`에 `opportunities` 메서드 추가(같은 이름·같은 반환 모양).
- [x] `A/marketing_ai.py`의 기존 문자 후보 함수는 건드리지 않고, 추천·컨텍스트는 성격별 모듈과 공통 규칙 엔진으로 분리해 충돌을 피했다.
- [x] AI 추천을 `1. AI 문자 추천`과 `2. 기타 AI 추천`으로 분리했다. 감사 혜택·재방문·휴면 복귀·생일 안내에만 문자 실행을 제공하고, 취향·시간대·메뉴·운영 추천은 현장 활용 문구로 변경했다. 카테고리별 네 개 순환·문자 대상/초안 연결·맨 아래 손님 응대 제안 유지까지 관련 화면 33개와 API 10개 테스트로 확인했다.
- [x] 2026-10-19 최종 전체 테스트: 서버 **293 passed, 1 skipped**, 화면·통합 **153 passed, 9 skipped**. 현재 반영된 채팅 세션 정렬 수정도 통과했다. 운영 Supabase 검증 범위는 아래에 별도로 기록한다.

### 3-2. 마케팅 DB 연동 점검 (2026-10-19)

**팀원 연결 방법**

- 백엔드의 `DATABASE_URL`이 데이터를 넣은 DB를 가리키고, 테이블·컬럼은 `docs/db/fbgrowth_schema.sql` 계약을 따라야 한다. 고객 파일을 폴더에 넣는 것만으로는 반영되지 않는다.
- 관리자 화면은 `DATA_SOURCE=api`로 실행한다. `dummy`는 시연 자료만 사용하고, `auto`는 최초 연결 실패 시 더미로 열릴 수 있으므로 실제 DB 검증에는 `api`를 사용한다. 이미 더미로 열린 화면은 API 모드로 다시 연결한다.
- 조회는 `admin/admin_repository.py`를 통해 이뤄진다. 고객·매출 집계는 재조회할 때 계산되며, 자동 푸시 방식은 아니다. F&B그로스는 **최신 데이터 반영**, AI 추천은 **재추천**, AI 문자는 화면 재실행·후보 재생성, 챗봇은 **새 질문** 시 최신 DB를 읽는다. 기존 문자 초안과 과거 채팅 답변은 작성 당시 내용이다.

| 영역 | 서버에서 읽는 코드 | DB 원본 |
|---|---|---|
| 고객 목록·등급 | `B/routers/admin/members.py`, `B/stores/members.py`, `B/stores/grade_rules.py` | `members`, `app_settings`의 저장된 등급 기준 |
| F&B 매출·그래프 | `B/stores/stats.py`, `B/services/stats.py`, `B/services/growth_performance.py` | `orders.total`, `orders.created_at`, `orders.ai_combo`, `members` |
| AI 마케팅 추천 | `B/services/opportunities.py`, `shared/opportunity_engine.py` | 위 고객·주문 + `order_items`, `order_item_components`, `menus`, `recommendation_events` |
| 손님 응대 제안 | `B/stores/customer_notes.py`, `B/services/customer_notes.py` | `members`, `orders`, 주문 메뉴, `table_logins`, 저장된 당일 날씨 |
| AI 문자 대상·문구 | `B/services/sms.py`, `B/services/sms_candidates.py` | 회원 전화번호·수신 동의·수신거부, 저장된 등급 기준, 메뉴·판매량; 발송 이력은 `sms_logs` |
| AI 챗봇 근거 | `B/services/chat.py`, `B/stores/stats.py` | 최신 주문·메뉴 판매량·회원; 대화 이력은 `chat_sessions`, `chat_messages` |

**검증 및 보완 내용**

- [x] `BT/test_seokwon_marketing_db_sync.py`의 대량 DB 변경·KST 경계·저장 등급 기준 테스트와 `T/test_seokwon_marketing_db_sync.py`의 성과 화면 갱신·문자 대상 유지 테스트를 전체 테스트와 함께 통과했다.
- 격리된 SQLite 테스트 DB에 회원 1,000명·회원/비회원 주문 1,000건을 넣고 고객 추가, 주문 추가·금액 변경, 문자 수신거부·동의 변경 후 다시 조회한다. 목록·추천 요약·문자 대상·챗봇 근거·성과 합계가 함께 변하는지 검증한다. 운영 DB에는 테스트 행을 넣지 않는다.
- 실제 API에 연결한 Streamlit 화면에서 새 회원·비회원 주문 추가 후 고객표·오늘 매출·월환산 매출·최종 차이·AI 주문 매출 비중이 함께 갱신되는지 검증한다.
- 실제 오늘 매출과 마지막 주문일 매출을 분리했고, UTC 주문을 KST로 변환해 시간대·요일 추천을 맞췄다. API에 응대 대상이 없으면 시연용 손님을 표시하지 않는다.
- AI 추천에서 선택한 문자 대상 ID를 유지한다. 이후 가입한 고객은 자동 선택하지 않고, 사장님이 직접 체크하면 추가할 수 있다. 실제 발송 대상은 서버에서 수신 동의·수신거부를 다시 검사한다.
- 휴면 고객의 재방문·단골 추천은 고정 2회/5회 대신 저장된 등급 기준을 따른다.

**해석·검증 범위**

- 오늘 지표는 KST 오늘, 최근 7·14·30일 분석은 **마지막 주문일 기준**이다. 화면에 기준 날짜를 표시한다. 회원 수만 늘려도 매출이 증가하지는 않으며, 실제 매출은 연결된 `orders`가 있어야 변한다.
- AI 도입일은 **최초 `ai_combo=true` 주문일**로 추정한다. 도입 전후 달력 일평균 × 30으로 월환산하며, 주문 없는 날짜는 0원으로 센다. 누락된 과거 자료와 실제 무매출일은 현재 스키마만으로 구분할 수 없다.
- 매출 증가액은 도입 전후 총매출의 차이이며, AI만의 인과적 효과를 입증한 값은 아니다. 휴면 복귀·신규 정착·방문 빈도 증가의 정확한 전환 성과에는 과거 등급/캠페인 노출·방문 연결 기록이 더 필요하다. 현재 화면의 재방문·단골 성과는 AI 주문과 **현재 등급**의 교집합인 임시 지표다.
- DB에 이미 들어간 시연 주문은 일반 주문과 함께 집계된다. 실제 데이터 전환 시 시연 행의 처리 범위는 팀이 결정해야 한다. 이번 점검에서는 삭제하지 않는다.
- Supabase 운영 인스턴스에 대한 실제 연결·외부 문자 전송·Gemini 응답 품질은 이번 자동 테스트 범위가 아니다. 챗봇은 `CHAT_OWNER_ID`와 Gemini 설정, 실제 문자 전송은 Solapi 설정이 별도로 필요하다.
