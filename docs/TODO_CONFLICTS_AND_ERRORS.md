# TODO 진행 중 예상 충돌·오류와 해결 방법

팀원 5명이 `todo/TODO_*.md`를 동시에 진행할 때 걸리기 쉬운 것을 **증상 / 원인 / 해결** 표로 모았습니다. 코드는 `main`(2026-10-16) 기준으로 확인했고, 확인하지 못한 것은 **(추정)** 으로 표시했습니다.

- 담당 약자: **성** 성호(QR·문자·챗봇) / **재** 재현(주문·룰렛·쿠폰·AI·날씨) / **수** 수용(통계·등급·알림) / **준** 서준(메뉴·카테고리) / **석** 석원(직원호출·룰렛설정·관리자 AI추천) / **전** 전원
- 이미 해결된 것은 뺐습니다. 예: `SERIAL_TABLES`에 `coupons`, `table_logins`, `staff_calls`, `orders`, `order_items`는 이미 들어 있습니다.

---

## 1. Git·파일 충돌

| 번호 | 증상 | 원인 | 해결 | 담당 |
|---|---|---|---|---|
| G1 | PR 머지 때 `backend/app/dummy.py` 충돌 | 더미 함수와 `DUMMY_ENDPOINTS` 줄이 한 파일에 붙어 있어 이웃한 줄을 지우면 겹침 | **내 함수와 내 `DUMMY_ENDPOINTS` 줄만** 지운다(빈 줄·이웃 줄은 그대로). PR을 작게 자주 보내고, 보내기 전에 `dev`를 먼저 받아 온다 | 재·수·준·석 |
| G2 | `backend/app/routers/user.py` 충돌 | 손님용 라우트(메뉴·주문·룰렛·쿠폰·직원호출·AI)가 한 파일 | 내 라우트 함수 안쪽만 고친다. 함수 순서 바꾸기·import 정렬 금지. 새 라우트는 파일 끝이 아니라 **관련 함수 바로 아래**에 추가하면 같은 위치 추가 충돌이 줄어든다 | 재·준·석 |
| G3 | `factory.py`, `routers/admin/__init__.py` 충돌 | 새 라우터 등록 줄을 여러 명이 같은 위치에 추가 | 새 라우터 파일이 필요하면 **한 사람씩 순서대로** 머지한다. 분배 문서의 "선작업 PR"(빈 라우터 등록)이 머지되기 전에는 이 두 파일을 서로 알리고 수정 | 전 |
| G4 | `PUT /admin/api/content/{name}`과 `seed/content.json`을 세 명이 고침 | `content`는 카테고리(준)·룰렛/직원호출 항목(석)·AI 질문/규칙(재)이 한 키 묶음 | 각자 **본인 키만** 지운다. 마지막에 남은 키가 없는지 한 사람이 정리한다 | 재·준·석 |
| G5 | `user/user_repository.py`, `admin/admin_repository.py`의 `ENDPOINTS`/호출 목록 충돌 | 화면 호출 모음이 한 파일 | 내 호출 줄만 추가·수정. 응답 모양은 더미와 같게 유지(계약 테스트가 확인) | 전 |
| G6 | `docs/DB_SCHEMA.md`, `docs/db/*.sql`, `AGENTS.md` 충돌 | 스키마·규칙 변경이 겹침 | 스키마를 바꾸는 사람은 한 명씩. 바꾸면 문서도 같은 PR에 넣고 팀에 알린다(AGENTS.md 금지 구역 규칙) | 전 |
| G7 | 같은 이름의 새 테스트 파일 | TODO 예시가 `test_roulette.py` 등 같은 이름 | 테스트 파일명은 본인 기능 이름으로. 예: 수용 `test_stats_db.py`, 서준 `test_menus_db.py` | 전 |
| G8 | PR을 `main`으로 보냄 | 포크 흐름 혼동 | PR은 본 리포 **`dev`로만**. 브랜치명은 `feat/한글설명` 형식. `main` 반영은 SEONGHO | 전 |
| G9 | 의존 순서가 어긋남 | 석원 룰렛 서비스 칸은 서준 메뉴, 수용 통계는 재현 주문, 성호 후보·챗봇은 수용·재현 데이터에 의존 | 순서: 서준 → 재현 → 수용·석원 → 성호. 아직 안 끝난 쪽 데이터는 "집계 전"/건너뛰기로 두고 TODO에 적힌 규칙을 따른다 | 전 |

---

## 2. 더미 교체·테스트 규칙

| 번호 | 증상 | 원인 | 해결 | 담당 |
|---|---|---|---|---|
| D1 | `dummy.xxx` 지웠더니 다른 라우터에서 `AttributeError` | 다른 라우터가 같은 더미를 같이 씀. 예: `routers/admin/orders.py`는 `dummy.members()`와 `dummy.orders()`, `routers/admin/menus.py`는 `dummy.content_item("categories")`를 씀 | 지우기 전에 `grep -rn "dummy\." backend/app`으로 **사용처를 전부** 찾아 함께 교체. 아직 못 바꾸는 쪽이 쓰는 함수는 남긴다 | 전 |
| D2 | `test_dummy_get.py` 실패 | 더미를 지우거나 모양을 바꾸면 이 테스트가 옛 응답을 기대 | 교체한 엔드포인트의 케이스를 **실제 DB 응답 기준으로 고쳐 쓴다**(삭제·skip 금지). 응답 모양은 더미와 같게 | 전 |
| D3 | skip 해제한 테스트가 깨짐 | `test_tablet_logins.py`(재), `test_coupons.py`(재), `test_shop_admin.py`(준) skip은 로직 구현 전제 | 구현을 끝낸 뒤 skip만 지운다. 안 맞으면 테스트를 지우지 말고 구현을 고친다. 구현 전에 skip을 지우면 `NotImplementedError`로 실패 | 재·준 |
| D4 | 루트 `python -m pytest tests -q`만 깨짐 | 화면 계약 테스트(`tests/test_admin_data_source.py` 등)가 서버 응답 모양을 확인 | 서버만 돌리고 끝내지 말고 **두 명령 모두** 통과를 확인 | 전 |
| D5 | `NotImplementedError` 500 | 라우터를 store 호출로 바꿨는데 store 뼈대가 아직 비어 있음 | store 메서드를 다 채운 뒤 라우터를 바꾼다. `ShopStore`는 메뉴·주문·호출·추천 믹스인을 합친 것이라 **같은 믹스인 파일은 한 명만** 맡는다 | 재·준·석 |
| D6 | `user/test_*.py`는 완료 기준에서 빠짐 | 두 테스트 명령의 범위 밖 | `cd user && python -m unittest test_ai_quiz test_cart test_recommendations`를 따로 돌린다 | 전 |

---

## 3. Postgres(Supabase) 전용 오류

로컬은 SQLite, Supabase는 Postgres입니다. 코드 SQL은 `?` 자리표시자·`INTEGER PRIMARY KEY AUTOINCREMENT`만 자동 변환(`stores/db.py` `translate`)하고, 그 밖의 차이는 직접 맞춰야 합니다. **SQLite 테스트가 통과해도 Postgres에서는 실패할 수 있습니다.**

| 번호 | 증상 | 원인 | 해결 | 담당 |
|---|---|---|---|---|
| P1 | `INSERT` 뒤 id가 `None` | `db.run`은 `SERIAL_TABLES`에 있는 테이블만 `RETURNING id`를 붙임. 아직 없는 것: `roulette_prizes`, `staff_call_items`, `quiz_options`, `chat_messages`, `alerts` | 해당 테이블에 INSERT 후 id가 필요하면 `stores/db.py`의 `SERIAL_TABLES`에 이름 추가(한 줄). 공용 파일이므로 **한 사람이 먼저 PR로 넣는다**(성호 제안). id가 필요 없으면 불필요 | 성·석·수 |
| P2 | `chat_sessions` INSERT 후 id를 못 받음 | id가 `uuid`(기본값 `gen_random_uuid()`)라 `SERIAL_TABLES` 방식이 안 맞음 | 코드에서 `uuid.uuid4()`로 만들어 INSERT하고 그 값을 반환(SQLite도 동일 동작) | 성 |
| P3 | `operator does not exist: boolean = integer` 또는 `column "is_soldout" is of type boolean but expression is of type integer` | SQLite 칸은 `INTEGER`, Postgres는 `boolean`. 대상: `is_soldout`, `set_ok`, `ai_combo`, `roulette_eligible` | SQL에 `0/1`을 쓰지 말고 **파라미터로 Python `bool`** 전달. 읽을 때는 `bool(row[...])`로 통일(SQLite는 0/1, Postgres는 True/False) | 준·재·석 |
| P4 | `tags`/`items` 저장 오류 또는 문자열 `'["a"]'`가 배열로 들어감 | Postgres는 `text[]`, SQLite는 JSON 문자열 | 저장은 `db.to_list(...)`, 읽기는 `db.from_list(...)`. 대상: `menus.tags`, `staff_calls.items`, 후속 `combo_ids` 등 | 준·재·석 |
| P5 | 시각 비교·정렬이 어긋남 | SQLite `CURRENT_TIMESTAMP`는 `2026-10-16 02:10:00`(공백), 코드가 넣는 ISO는 `...T...`. 문자열 비교에서 섞이면 순서가 틀림. Postgres는 `timestamptz`라 `db.all`이 ISO로 바꿔 줌 | 시각은 **항상 코드에서 ISO 문자열(UTC)** 로 넣는다(`issued_at` 방식). `DEFAULT CURRENT_TIMESTAMP`에 기대 비교하지 않는다 | 재·수 |
| P6 | 통계 SQL이 Postgres에서만 실패 | SQLite 함수(`strftime`, `date('now')`, `INSERT OR IGNORE/REPLACE`, `GROUP_CONCAT`)는 `translate`가 바꾸지 않음 | 날짜 집계는 SQL이 아니라 **Python에서 KST로 계산**하거나, 양쪽에서 되는 표준 SQL(`ON CONFLICT ... DO UPDATE`, `COALESCE`, `CASE`)만 쓴다 | 수·재 |
| P7 | `LIKE '%…%'`가 깨짐 | `translate`가 `%`를 `%%`로 바꾸고 `?`를 `%s`로 바꿈 | 패턴은 SQL에 직접 쓰지 말고 파라미터로 넘긴다(`LIKE ?` + `"%키워드%"`). SQL에 `?` 글자를 문자열 안에 쓰지 않는다 | 전 |
| P8 | 여러 문장 스키마가 Postgres에서 오류 | `db.script`가 Postgres에서는 `;`로 문장을 나눔 | 새 `SCHEMA` 안에 문자열·트리거·함수 본문의 `;`를 넣지 않는다. 트리거·함수는 SQL Editor에서 별도로 적용 | 전 |
| P9 | `psycopg.errors.UniqueViolation` | 유니크 제약이 SQLite 스키마보다 많음: `table_logins (table_no, member_id, login_day)`, 룰렛 하루 1회 부분 인덱스(`table_logins_one_play_per_day`), `coupons.table_login_id` | 룰렛 1회·쿠폰 1장은 제약 위반을 **잡아서 409/422로 변환**한다. 사전 조회만 믿지 않는다(동시 요청) | 재 |
| P10 | `psycopg.errors.ForeignKeyViolation` | Supabase에는 FK가 있고 SQLite에는 없음. 메뉴를 쓰는 룰렛 서비스 칸(`roulette_prizes.menu_id`, RESTRICT), 메뉴가 남은 카테고리(`menus.category_id`, RESTRICT), 없는 `menu_id`로 쿠폰·주문 줄 INSERT | 삭제 전에 사용 여부를 조회해 **409와 안내 문구**로 거절하거나 예외를 잡아 변환. 시드는 순서 지키기: categories → menus → roulette_prizes | 준·석·재 |
| P11 | `ai`/`best` 카테고리에 메뉴 저장 시 DB 예외 | `menus_virtual_check` 트리거가 가상 카테고리를 막음(SQLite에는 없음) | 라우터에서 **먼저 422**로 거절(DB 예외에 의존하지 않기) | 준 |
| P12 | `check constraint` 위반 | Postgres에만 있는 체크: `weight 0~100`, `spicy 0~3`, `qty 1~99`, 룰렛 칸 `kind`별(할인=percent 필수·menu_id 없음 / 서비스=menu_id 필수) , 쿠폰 `kind`별 | 서버 검증(Pydantic `Field`)을 DB 체크와 **같은 범위**로 맞춘다 | 준·석·재 |
| P13 | `DATABASE_URL`이 Postgres일 때만 로그인·문자 실패 | 현재 서버·테스트는 Supabase에서 한 번도 실행된 적이 없음(DB_SCHEMA.md 검증 이력 참고) | 개발 중 SQLite로 하더라도, **PR 전 한 번은 Supabase 연결로** 해당 기능을 수동 확인. 연결 문자열은 팀 비공개 채널로 공유하고 `backend/.env`에만 넣음(커밋 금지) | 성(스모크 테스트), 전 |
| P14 | 서버 시작 때 `prepared statement` 오류 (추정) | Supabase 풀러 모드에 따라 다름. 코드는 `prepare_threshold=None`으로 대비함 | "Session pooler" 주소를 쓴다(`.env.example` 주석 참고) | 전 |
| P15 | Supabase에 이미 있는 테이블과 SQLite `SCHEMA`의 칸이 다름 | `CREATE TABLE IF NOT EXISTS`는 이미 있는 테이블을 **고치지 않음**. SQLite 코드 칸이 Supabase에 없으면 `column does not exist` | 새 칸이 필요하면 SQL Editor에서 `alter table` 직접 실행 + `docs/DB_SCHEMA.md`·`docs/db/*.sql` 수정 + 팀 공지. 로컬은 `backend/app.db`를 지우고 서버 재시작 | 전 |
| P16 | SQLite에만 있는 테이블 | 새 기능 테이블(`categories`, `roulette_prizes`, `staff_call_items`, `quiz_*`, `alerts`, `chat_*`)은 SQLite용 `SCHEMA`가 아직 없음 | 로컬 테스트용으로 store에 `SCHEMA`(SQLite 문법)를 추가하되 **컬럼명을 Supabase 스키마와 동일하게** 한다 | 준·석·재·수·성 |

---

## 4. 데이터·FK·RLS·환경변수

| 번호 | 증상 | 원인 | 해결 | 담당 |
|---|---|---|---|---|
| E1 | Supabase로 돌리면 메뉴 5개·카테고리 5개만 나옴 (2026-10-16 점검 기준, 이후 변경 미확인) | Supabase 시드가 축소판인데 `seed_menus()` 등은 "비어 있을 때만" 시드 | 전체 시드 SQL(`menu.json` 60개 기준)을 SQL Editor에서 실행하거나 축소판 행을 비우기. **DB를 바꾸므로 SEONGHO 결정 후** 실행. 현재 DB 행 수는 다시 확인 필요 | 준·석·재·성 |
| E2 | 전체 메뉴 시드 때 FK 오류 | 카테고리 `soup`·`beer`·`soju`가 없음 (2026-10-16 점검 기준) | categories → menus → roulette_prizes → staff_call_items → quiz_* → recommendation_rules 순서로 넣는다 | 준·석·재 |
| E3 | 챗봇 세션 생성 때 `owner_id` NOT NULL / FK 오류 | `chat_sessions.owner_id`가 `auth.users` 참조이고 `owners`는 비어 있음. 관리자 인증은 마지막 단계 | 임시로 `auth.users`의 계정 uuid를 환경변수(예: `CHAT_OWNER_ID`)로 받는다. 코드에 상수로 박지 않는다. 인증 단계에서 교체. 스키마 완화는 비권장 | 성 |
| E4 | 주문 줄의 `menu_id`가 모두 null, 인기메뉴가 이상함 | 존재하는 메뉴 id만 연결하는데 메뉴 시드가 적음 | 메뉴 시드(E1)를 먼저 맞춘 뒤 주문 저장을 확인 | 재·수 |
| E5 | 쿠폰이 룰렛 기록과 연결되지 않음 | `coupons.issue(...)`에 `table_login_id`·`prize_id`가 없음. 스키마는 `table_login_id` UNIQUE | 재현이 시그니처를 정해 `table_login_id`·`prize_id`(선택)를 받게 하고 석원에게 알린다. 화면이 칸 id를 모르면 둘 다 null 허용 | 재·석 |
| E6 | 브라우저(anon 키)로 읽으면 빈 결과, 서버에서는 읽힘 | 모든 테이블 RLS 켜짐. 서버는 서비스 롤로 접속해 우회 | 서버 코드는 정상. 손님 앱이 Supabase를 직접 부르게 바뀔 때만 정책 추가. 정책이 없는 테이블에서 INFO 경고가 나오는 것은 의도된 상태 | 전 |
| E7 | 옛 테이블 `content`·`calls`·`tablet_logins`가 RLS 꺼진 채 남음 (2026-10-16 점검 기준 추정, 현재 미확인) | 이전 구조의 잔재 | 시드 원본으로 쓴 뒤 삭제하거나 최소한 RLS 켜기. **삭제는 되돌릴 수 없으므로 SEONGHO 확인 후** | SEONGHO |
| E8 | 서버 시작 시 `APP_ENV=prod`에서 `RuntimeError` | `JWT_SECRET`/`ADMIN_TOKEN`이 `change-me` | 운영 값으로 교체. 로컬은 `APP_ENV=dev` | 전 |
| E9 | 챗봇·문자 후보 호출이 인증 오류 | `GEMINI_API_KEY`가 `.env.example`에 없음. 후보 생성은 현재 `ANTHROPIC_API_KEY`(관리자 화면이 읽음) | `Settings`와 `.env.example`에 키 이름을 같이 추가(키 값은 커밋 금지). 후보를 서버로 옮길 때 Gemini로 통일할지 결정 | 성 |
| E10 | 같은 날 설정 값이 다름 | 등급 기준·문자 한도가 DB `app_settings`와 `Settings`(환경변수) 두 곳. 서버는 환경변수만 읽음 | 서버는 `Settings` 기준으로 통일하고 `app_settings` 값은 쓰지 않는다 | 수·성 |
| E11 | 서버를 재시작하면 QR 로그인 세션이 사라짐 | 로그인 대기 세션이 메모리(`LoginSessionStore`)에 있음 | 시연은 서버 1대·짧은 유효시간(180초)이라 무방. 서버 여러 대로 늘릴 때만 DB로 이전 | 성 |
| E12 | 문자 수신자 기록이 비어 있음 | `SmsLogStore.add`는 `sms_logs`만 저장하고 `sms_log_recipients`는 저장하지 않음 | 필요할 때 `add` 뒤에 수신자 INSERT 추가(시연엔 불필요) | 성 |

---

## 5. 기능별로 자주 걸리는 순서 문제

| 번호 | 증상 | 원인 | 해결 | 담당 |
|---|---|---|---|---|
| F1 | `/customers/grades`가 `/customers/{id}/…`로 처리됨 | 고정 경로를 가변 경로 뒤에 선언 | 고정 경로를 **먼저** 선언 | 수 |
| F2 | 테이블 누적 주문 합계가 이전 손님 주문까지 포함 | `table_logins` 로그인 시각 이후만 합산해야 함 | `table_sessions` 같은 새 테이블을 만들지 말고 로그인 시각 조건으로 조회 | 재 |
| F3 | 룰렛이 같은 날 두 번 돌아감 | 하루 1회는 회원 기준(KST). 다른 테이블이어도 불가 | `login_day`는 KST 날짜. 위반은 P9처럼 DB 제약 + 사전 조회 둘 다 | 재 |
| F4 | 주문 상태(접수/조리중)를 만들고 싶어짐 | — | 제품 규칙상 **상태 기능·UI 없음**. 만들지 않는다 | 전 |
| F5 | 룰렛 칸 통째 교체 중 쿠폰·로그인 기록이 끊어질까 걱정 | `coupons.prize_id`, `table_logins.prize_id`는 `ON DELETE SET NULL` | 삭제 후 삽입으로 교체해도 안전. 한 트랜잭션 없이 `db.run` 반복이므로 삽입 도중 실패 시 칸이 비는 점은 주의(추정: 시연 규모에서는 문제 적음) | 석 |

---

## 6. 막혔을 때 확인 순서

1. `grep -rn "dummy\." backend/app/routers`로 아직 더미인 라우트 확인
2. 오류 메시지의 `psycopg.errors.…` 이름으로 위 표(P·E)에서 찾기
3. `docs/DB_SCHEMA.md`와 `docs/db/fbgrowth_schema.sql`에서 제약·타입 확인
4. 그래도 안 풀리면 PR 대신 팀 채널에 오류 전문과 실행한 SQL을 공유(비밀 키·DB 비밀번호 제외)
