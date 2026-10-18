# 재현 TODO · 손님 AI 추천 질문 · 룰렛 · 쿠폰 · 주문(주문 이력 포함)

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
| 1 | 1. 매장 정보 | `GET /api/v1/store` | 완료 |
| 2 | 2. 주문 저장 · 테이블 누적 · 주문 이력 | `POST /api/v1/orders`, `GET /api/v1/tables/{id}/orders`, `GET /api/v1/owner/orders` | 완료 |
| 3 | 3. 룰렛 · 쿠폰함 | `roulette/status·plays`, `tables/{n}/logins/prize`, `coupons`, `tables/{n}/coupons`, `POST /api/orders`(쿠폰 사용) | 완료 |
| 4 | 4. AI 질문 · 추천 · 날씨 · 규칙 | `ai/questions`, `ai/recommendations`, `weather/current`, `ai/recommendation-rules` | 완료(4-3 선택 제외) |

**다른 팀원과 겹치는 지점**

| 파일 | 누구와 | 규칙 |
|---|---|---|
| `B/stores/shop_orders.py` | 수용(통계가 주문을 읽음) | 재현만 수정. 수용은 `B/stores/stats.py`(신규)에서 따로 읽는다 |
| `B/stores/roulette_prizes.py`(신규, 석원) | 석원 | 재현은 `list()`만 호출. 시그니처는 석원과 먼저 합의 |
| `B/services/weather.py`(신규) | 성호가 가져다 씀 | 재현이 먼저 만들고 성호는 import만 한다. 함수 이름이 바뀌면 알려 준다 |
| `B/routers/` | 서준(`menus.py`), 석원(`staff_calls.py`) | 본인 파일만 수정. 재현은 `store.py`·`orders.py`·`coupons.py`·`roulette.py`·`ai.py`. 쿠폰함·룰렛이 쓰는 `tablet_rows`는 `user.py`(성호 파일)에서 가져다 쓰기만 한다 |
| `B/dummy/` | 서준·수용·석원 | 본인 담당 `*_data.py`의 함수·`ENDPOINTS` 줄만 다룬다 (`store_data`, `coupon_data`, `order_data`, `recommend_data`) |

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

## 1. 매장 정보 (더미)

### 1-1. `GET /api/v1/store`

**목표**: 스플래시·헤더에 보이는 매장 이름·지점·슬로건·테이블 수를 DB(`store_info`)에서 읽어 돌려준다.

**테스트 방법**: `BT/test_store_endpoint.py`(이미 있음)가 통과하는지 확인 → `GET /api/v1/store` 응답 키가 `name, branch, slogan, tables`인지 → `STORE_NAME=테스트` 환경변수로 서버를 띄워 값이 바뀌는지 수동 확인.

**중요 이론**: 읽기 전용 GET은 "라우터 → 서비스/스토어 → DB" 한 줄로 끝난다. `app.state.store_info`는 서버 시작 때 한 번 만들어 모든 요청이 공유한다 (`B/factory.py`).

**흐름**
```
UI(스플래시 매장명) → U/user_repository.py _fetch_content → GET /api/v1/store
 → B/routers/store.py store_info → B/stores/store_info.py get() → DB(store_info 1행)
 → {name, branch, slogan, tables} → U/state/context.py STORE → UI 매장명·지점
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `B/routers/store.py`의 `dummy.store()` 줄, `B/dummy/store_data.py`의 `store()`와 `ENDPOINTS`의 `"GET /api/store, /api/v1/store"` 줄.
- [x] 라우터에서 `request.app.state.store_info.get()`을 돌려준다(`StoreInfoStore.get`은 이미 구현돼 있음).
- [x] `BT/test_dummy_get.py`의 `test_user_get_dummies`에서 store 줄을 빼고, `BT/test_store_endpoint.py`로 대체됐는지 확인.

---

## 2. 주문 (완료)

### 2-1. `POST /api/v1/orders` (= `POST /api/orders`)

**목표**: 손님이 장바구니를 주문하면 `orders`·`order_items`(·`order_item_components`)에 저장한다. 로그인 회원이면 `member_id`를 붙이고, 줄 id가 `combo:`로 시작하면 AI 조합 주문(`ai_combo=true`)이다. 쿠폰 사용 처리는 3-4에서 같은 함수에 이어 붙인다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| 새 `BT/test_orders.py` | 비회원 주문 201 + DB 저장, 회원 주문은 `member_id` 저장, 줄이 비면 422, `combo:` 줄이 있으면 `ai_combo=true`, 조합 구성 메뉴가 `order_item_components`에 저장 |
| 기존 `BT/test_shop_admin.py::test_orders_calls_and_member_link`의 `skip` | 주문·관리자 이력 연결이 되면 해제 |
| 수동 | 손님 화면에서 메뉴 담고 주문 → 관리자 > 주문 이력에 나타남 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 1:N 저장 | 주문 1건(`orders`) 아래 줄 여러 개(`order_items`), 조합 줄 아래 구성 메뉴(`order_item_components`). 부모를 먼저 저장하고 새 `id`로 자식을 저장한다 |
| 트랜잭션 | 주문과 줄 저장 중 하나만 실패하면 전부 취소해야 한다. 한 번에 커밋하거나 모두 롤백 |
| 가격 사본 저장 | 메뉴 이름·단가를 주문 줄에 복사해 둔다. 나중에 메뉴가 바뀌거나 지워져도 과거 주문이 유지된다 |
| 서버 재계산 | 화면이 보낸 `total`을 그대로 믿지 말고 줄 합계와 비교하는 검증을 고려한다(쿠폰 할인 반영 전/후 규칙을 팀과 확인) |

**흐름**
```
UI(주문 확인 다이얼로그 · 주문하기) → U/ui/dialogs.py → ctx.REPO.create_order (U/user_repository.py)
 → POST /api/orders {table_no, lines, total, coupon_ids} (+Bearer 토큰이 있으면 회원)
 → B/routers/orders.py create_order → B/stores/shop_orders.py add_order
 → DB: orders INSERT → order_items INSERT(줄마다) → order_item_components INSERT(조합 구성)
 → {no, ai_combo, used_coupon_ids} → UI "주문 번호 N" + 장바구니 비우기
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `create_order`의 `dummy.order_created(...)` 줄, `B/dummy/order_data.py`의 `order_created`와 `"POST /api/orders"` 줄.
- [x] `B/stores/shop_orders.py`의 `add_order`, `order`, `orders` 구현(파일 안 TODO 주석 그대로). `menus`에 있는 id만 `menu_id`로 연결, 없으면 null.
- [x] 라우터 TODO대로 `shop.add_order(table_no, lines, total, member_id)` 호출.
- [x] 주의: `ShopStore`가 메뉴를 쓰려면 서준의 `seed_menus()`가 필요하다. 서준 작업 전에는 `menu_id`를 null로 두고 테스트한다.
- [x] 화면 변경은 필요 없다(응답 `{no, ai_combo, used_coupon_ids}` 모양 유지).

### 2-2. `GET /api/v1/tables/{tableId}/orders` (완료)

**목표**: 주문내역 다이얼로그에 "이 테이블에서 지금까지 시킨 것"을 합계와 함께 보여준다. **`table_logins`의 로그인 시각 이후 주문만** 합산한다 (손님이 바뀌면 이전 손님 주문이 안 섞이게. `table_sessions` 테이블은 만들지 않는다).

**테스트 방법**: 새 `BT/test_orders.py`에 추가 — 로그인 전에 만든 주문은 빠지고 로그인 이후 주문만 합계에 들어간다 / 다른 테이블 주문은 안 섞인다 / 로그인 기록이 없으면 빈 목록.

**중요 이론**: 시간 조건 조회(`created_at >= 기준시각`), 기준시각은 "이 테이블의 가장 이른 유효 로그인 시각"(`table_logins.logged_in_at`, 유효시간 `JWT_EXPIRE_MINUTES` 이내). 시각은 UTC ISO 문자열로 저장되어 문자열 비교가 가능하다.

**흐름**
```
UI(🧾 주문내역 버튼) → U/ui/dialogs.py → (새) server.table_orders → GET /api/v1/tables/{n}/orders
 → B/routers/orders.py(신규) → B/stores/tablet_logins.py 로 기준 시각 조회 → B/stores/shop_orders.py 기간 조회
 → DB(table_logins, orders, order_items) → {orders:[...], total} → UI 주문내역 + 합계
```

**상세 설명 / TODO**

- [x] `B/stores/shop_orders.py`에 `table_orders(table_no, since)` 추가, `B/stores/tablet_logins.py`에 기준 시각 조회 함수 추가(둘 다 재현 파일).
- [x] 화면: 지금 주문내역은 세션(`ss.orders`)에서 그린다. 서버 값으로 바꿀 때 `U/user_repository.py`에는 새 메서드만 추가한다.

### 2-3. `GET /api/v1/owner/orders` (관리자 주문 이력)

**목표**: 관리자 > 주문 이력의 전체 주문·고객별 주문을 DB에서 읽는다. `member_id` 필터를 지원한다. 기간·테이블·금액·AI 사용 필터는 현재처럼 화면(`A/order_filters.py`)에서 처리한다.

**테스트 방법**: 새 테스트 — 주문 3건 저장 후 목록 최신순, `?member_id=`로 그 회원 주문만, 인증 없으면 401, 응답에 `nickname`(비회원은 null). 화면 쪽은 `python -m pytest tests/test_order_filters.py -q`가 그대로 통과.

**중요 이론**: JOIN으로 회원 닉네임을 붙인다(`orders LEFT JOIN members`), 비회원은 `member_id`가 null이라 LEFT JOIN이 필요하다. 인덱스 `orders_created_idx`가 최신순 조회를 빠르게 한다.

**흐름**
```
UI(주문 이력 탭) → A/views/orders.py → repo.orders() (A/admin_repository.py) → GET /admin/api/orders?member_id=
 → B/routers/admin/orders.py → B/stores/shop_orders.py orders() → DB(orders + order_items + members)
 → [{id, ts, table_no, total, lines, ai_combo, member_id, nickname}] → pandas 표 → UI 표 + 필터
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `B/routers/admin/orders.py`의 `dummy.orders()`/`dummy.members()` 사용부, `B/dummy/order_data.py`의 `orders`·`members`(수용의 통계 더미가 `members`를 쓰므로 수용과 순서를 맞춘다)와 `"GET /admin/api/orders"` 줄.
- [x] 응답 모양은 `dummy.orders()`와 같게 유지(키: `id, table_no, member_id, total, roulette_discount_percent, ai_combo, recommendation_event_id, ts, lines`).

---

## 3. 룰렛 · 쿠폰함 (완료)

**규칙(바꾸지 말 것)**: 룰렛은 회원당 하루 1회(KST). 같은 날 다른 테이블에서도 불가, 다음 날은 가능. 당첨은 즉시 적용하지 않고 `coupons`(쿠폰함)에 넣고, 주문 화면 쿠폰함에서 사용/취소하며 주문 시 `used_at`을 기록한다. 유효기간은 미정(`expires_at` null).

### 3-1. `PUT /api/tables/{tableNo}/logins/prize` (당첨 기록 + 쿠폰 발급)

**목표**: 룰렛 결과를 `table_logins`에 기록하고 쿠폰을 발급한다. 이미 돌린 회원은 409.

**테스트 방법**: 기존 skip 된 `BT/test_tablet_logins.py`, `BT/test_coupons.py`의 `skip`을 해제하고 통과시킨다. 확인 항목: 이 태블릿 로그인 회원이 아니면 404 / 하루 두 번째면 409 / `kind=discount`인데 `percent` 없으면 422 / 서비스 쿠폰은 `item_id` 필수 / 성공 시 쿠폰이 `coupons`에 1장.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| KST 하루 경계 | DB는 UTC로 저장하므로 "오늘 0시(KST)"를 UTC로 바꿔 비교한다 (`B/stores/coupons.py _today_start_utc` 참고) |
| 중복 방지 | 코드 검사만으로는 동시에 두 번 누르면 뚫린다. DB의 부분 유니크 인덱스 `table_logins_one_play_per_day`가 마지막 방어선이다 |
| HTTP 상태 | 404=없음, 409=이미 처리됨(충돌), 422=입력값 오류 |
| 발급 후 사본 저장 | 쿠폰에 `label`·`emoji`를 복사해 둬 룰렛 칸 설정이 바뀌어도 쿠폰은 그대로 |

**흐름**
```
UI(룰렛 돌리기) → U/ui/roulette.py → U/state/roulette.py spin_roulette → U/server.py play_roulette
 → PUT /api/tables/{n}/logins/prize {member_id, prize, kind, percent|item_id}
 → B/routers/roulette.py tablet_login_prize → (검사) B/stores/coupons.py issued_today → B/stores/tablet_logins.py set_prize
 → B/stores/coupons.py issue → DB(table_logins UPDATE, coupons INSERT) → {ok, coupon}
 → U/state/coupons.py add_coupon → UI 쿠폰함에 쿠폰 추가
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `tablet_login_prize`의 `dummy.prize_saved(...)`, `B/dummy/coupon_data.py`의 `prize_saved`·`"PUT /api/tables/{table_no}/logins/prize"` 줄.
- [x] `tablet_logins.set_prize`, `coupons.issue`, `coupons.get` 구현(파일 안 TODO). 라우터 TODO 1~5 순서대로.
- [x] **쿠폰과 룰렛 칸 연결**: `set_prize`가 기록한 `table_logins` 행 id를 `coupons.issue`의 `table_login_id`로 연결하고, `prize_id`도 선택적으로 저장한다. 부분 유니크 인덱스로 룰렛 1회당 쿠폰 1장을 보장한다.
- [x] `coupons.issued_today`와 `tablet_logins.record/list`의 기존 QR 로그인 연동을 유지한다.

### 3-2. `GET /api/v1/roulette/status`, `POST /api/v1/roulette/plays`

**목표**: `status`는 "남은 기회·회원별 참여/당첨 상태", `plays`는 **서버가 당첨 칸을 정한다**. 지금은 화면(`U/state/roulette.py pick_prize_index`)이 직접 랜덤을 뽑고 서버는 결과만 받아 적는다. 서버가 결정하게 바꿔 조작을 막는다.

**테스트 방법**: 새 `BT/test_roulette.py` — 가중치 0인 칸은 절대 안 나옴(`random`을 `monkeypatch`로 고정) / 하루 2회째 409 / 결과에 칸 번호와 할인율 또는 서비스 메뉴 id / 칸 구성은 석원의 store에서 읽는다.

**중요 이론**: 가중치 확률 추첨 `random.choices(weights=...)`(확률 = 가중치 / 가중치 합, 합이 0이면 균등). **결과는 반드시 서버에서 결정**(클라이언트는 연출만). 결정과 저장(`set_prize`+`issue`)은 한 번에 처리해 중간 실패 시 쿠폰만 생기는 일을 막는다.

**흐름**
```
UI(룰렛 돌리기 버튼) → U/state/roulette.py spin_roulette → (새) server.play_roulette
 → POST /api/v1/roulette/plays → B/routers/roulette.py(신규)
 → [하루 1회 검사 coupons.issued_today] → B/stores/roulette_prizes.py list()(석원) → 가중치 추첨
 → tablet_logins.set_prize + coupons.issue → DB → {index, prize, coupon}
 → U/ui/roulette.py 회전 각도 계산·애니메이션 → UI 당첨 안내 + 쿠폰함
```

**상세 설명 / TODO**

- [x] 3-1을 먼저 끝낸다. `plays`는 3-1의 검사·저장 코드를 `_save_prize`로 재사용한다.
- [x] `status` 응답: 이 태블릿 로그인 회원별 `{id, nickname, eligible, prize}`와 `spins_left`·`remaining`을 반환한다.
- [x] 화면은 서버가 결정한 결과로 회전하고, 서버가 안 닿을 때만 로컬 추첨을 대체 경로로 사용한다.
- [x] `roulette_prizes.list()`의 서버 설정을 추첨에 사용한다.

### 3-3. `GET /api/v1/coupons`, `GET /api/tables/{tableNo}/coupons`

**목표**: 내 쿠폰 목록(안 쓴 것 먼저)과, 이 태블릿에 로그인한 회원들의 쿠폰함(닉네임 포함).

**테스트 방법**: `BT/test_coupons.py`의 skip 해제분 + 추가 — 안 쓴 쿠폰이 먼저, 그 안에서 최근 발급순 / 로그인하지 않은 태블릿(`/tables/2/coupons`)은 403 / 다른 회원 쿠폰은 안 보임.

**중요 이론**: 정렬 `ORDER BY used_at IS NOT NULL, id DESC`(안 쓴 것 먼저). `JOIN members`로 닉네임을 붙인다. 접근 권한 검사(`_tablet_rows`)는 데이터 조회보다 먼저.

**흐름**
```
UI(🎟️ 쿠폰함 팝업) → U/ui/coupons.py → U/state/coupons.py load_coupons → server.table_coupons
 → GET /api/tables/{n}/coupons → B/routers/coupons.py table_coupons (user.py 의 tablet_rows 로 접근 확인)
 → B/stores/coupons.py for_members → DB(coupons JOIN members) → [{id, member_id, nickname, kind, label, used_at...}]
 → UI 쿠폰 카드(사용/취소 버튼)
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `my_coupons`, `table_coupons`의 `dummy.*` 줄과 `B/dummy/coupon_data.py`의 관련 함수·`ENDPOINTS` 줄.
- [x] `coupons.for_member`, `coupons.for_members` 구현. 두 라우트의 별칭(`/v1/coupons`, `/coupons`)은 그대로 둔다.

### 3-4. `POST /api/orders` 쿠폰 사용 (`coupon_ids`)

**목표**: 주문할 때 보낸 `coupon_ids`를 "내 쿠폰이고 아직 안 쓴 것"만 사용 처리(`used_at`, `used_order_id` 기록)한다.

**테스트 방법**: 쿠폰 발급 → 주문에 `coupon_ids` → `used_at` 채워짐 / 같은 쿠폰으로 두 번 주문하면 두 번째는 사용 처리 안 됨 / 다른 사람 쿠폰 id는 무시.

**중요 이론**: 권한 확인(이 태블릿에 로그인한 회원의 쿠폰만), 멱등성(이미 쓴 것은 건드리지 않음 → 응답 `used_coupon_ids`에 실제 처리된 것만).

**흐름**
```
UI(주문하기) → U/state/coupons.py pending_coupon_ids → create_order(coupon_ids)
 → POST /api/orders → create_order(2-1) → B/stores/coupons.py use(coupon_ids, member_ids, order_id)
 → DB(coupons UPDATE used_at, used_order_id) → {used_coupon_ids} → U/state/coupons.py consume_applied → UI 쿠폰 '사용 완료'
```

**상세 설명 / TODO**

- [x] `coupons.use` 구현 후 2-1의 `create_order`에서 호출. 같은 id가 중복으로 와도 한 번만 처리한다.
- [x] `BT/test_dummy_get.py::test_user_write_dummies`에서 본인 기능 줄(주문·쿠폰·prize)을 빼고 실제 DB 테스트로 대체했다.

---

## 4. AI 질문 · 추천 · 날씨 · 규칙

현재 구조: 질문·날씨·규칙은 DB 기반의 개별 API에서 받고, **추천 조합 계산은 화면 코드**(`U/recommendations.py recommend_combos`)가 한다. 서버는 노출 기록을 `recommendation_events`에 저장한다(`POST /api/v1/ai/recommendations`, 기존 경로 별칭 유지).

**단계로 나눠 진행한다**: ① 읽기 API 3개 ② 노출 기록 저장 ③ (선택) 추천 계산을 서버로.

### 4-1. `GET /api/v1/ai/questions`, `GET /api/v1/weather/current`, `GET /api/v1/ai/recommendation-rules`

**목표**: 질문(단계별 선택지), 현재 날씨, 추천 규칙을 DB 테이블(`quiz_questions`+`quiz_options`, `weather_types`+`weather_current`, `recommendation_rules`)에서 읽어 지금 화면이 받는 모양과 **똑같이** 돌려준다.

**테스트 방법**: 새 `BT/test_ai_content.py` — 응답이 `U/ai_quiz_data.py`·`U/recommendation_data.py`와 같은 모양이다 / 질문은 `sort_order` 순 / 옵션이 질문 아래로 묶임 / 날씨는 `{current, types:{코드:{label, icon}}}`. 화면: `python -m pytest user/test_ai_quiz.py user/test_recommendations.py -q` 통과.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 부모-자식 묶기 | 질문 1줄 + 선택지 N줄을 조회해 파이썬에서 `{..., options:[...]}`로 묶는다 |
| JSON 컬럼(`jsonb`) | 모양이 복잡한 규칙은 키별로 JSON 한 덩어리로 저장한다(`recommendation_rules.value`) |
| 응답 모양 = 명세 | 화면이 이미 쓰는 JSON 모양(`U/ai_quiz_data.py`, `U/recommendation_data.py`)이 곧 정답이다. 모양을 바꾸면 화면이 깨진다 |
| 외부 날씨 API | 호출 한도·장애에 대비해 마지막 값을 `weather_current`에 저장해 두고 그것을 돌려준다 |

**흐름**
```
UI(AI 질문 시작) → U/views/ai.py → ctx.QUESTIONS/WEATHER/RULES ← U/user_repository.py load_content
 → GET /api/v1/ai/questions · /weather/current · /ai/recommendation-rules
 → B/routers/ai.py(신규) → B/stores/ai_content.py(신규) / B/services/weather.py(신규)
 → DB(quiz_questions, quiz_options, weather_current, recommendation_rules)
 → 같은 모양의 JSON → UI 질문 카드 · "날씨 ○○" 표시
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `/content`의 `quiz_questions`·`weather`·`rules` 항목은 `/api/content`에서 나오므로, 새 API로 옮긴 뒤 `B/seed/content.json`에서 **본인 키(`quiz_questions`, `weather`, `rules`)만** 지운다(다른 키는 서준·석원이 지움).
- [x] 초기 데이터: `U/ai_quiz_data.py`, `U/recommendation_data.py`를 시드 원본으로 읽어 테이블에 채우는 시드 코드를 `B/stores/ai_content.py`에 두었다(비어 있을 때만 채움).
- [x] 질문(`quiz_questions`)과 추천 규칙(`recommendation_rules`)의 **내용은 담당자가 직접 정한다.** 4-4에서 A(규칙 기반 점수) 방식을 선택하고, 현재 화면의 8개 질문과 전체 추천 규칙을 시드했다.
- [x] `B/services/weather.py`(신규): 외부 날씨 API 연동 전에는 `weather_current`의 값을 읽기만 하도록 `current_weather(store) -> {code, label, icon}`을 추가했다.
- [x] `U/user_repository.py`: 질문·날씨·규칙·추천 기록만 새 `/api/v1/...` 경로로 바꾸고, 메뉴·룰렛·직원 호출 경로는 건드리지 않았다.

### 4-2. `POST /api/v1/ai/recommendations` (추천 기록 저장)

**목표**: 손님에게 추천 조합이 노출된 사실을 `recommendation_events`에 저장한다(관리자 AI 적중률의 분모). 지금 화면은 `POST /api/recommendations`로 이미 호출 중이다.

**테스트 방법**: 새 테스트 — 저장 후 `recommendation_count()`가 1 늘어난다 / `params`가 JSON으로, `combo_ids`가 리스트로 저장된다 / 비회원도 저장(`member_id` null). 수용의 통계가 이 개수를 읽는다.

**중요 이론**: 이벤트 로그 저장(쓰기 전용 기록). 화면이 같은 결과를 반복 렌더링해도 한 번만 기록하는 방어가 화면에 이미 있다(`U/views/ai.py log_recommendation`의 `last_rec_key`).

**흐름**
```
UI(추천 조합 카드 표시) → U/views/ai.py log_recommendation → ctx.REPO.log_recommendation
 → POST /api/recommendations → B/routers/ai.py log_recommendation → B/stores/shop_recommendations.py add_recommendation
 → DB(recommendation_events INSERT) → {id}
```

**상세 설명 / TODO**

- [x] 더미 주석처리: `log_recommendation`의 `dummy.recommendation_logged()`, `B/dummy/recommend_data.py`의 `recommendation_logged`·`"POST /api/recommendations"` 줄.
- [x] `add_recommendation`, `recommendation_count` 구현(파일 안 TODO). 새 경로 `/api/v1/ai/recommendations`를 `B/routers/ai.py`에 연결하고 기존 경로 별칭도 유지했다.
- [ ] `orders.recommendation_event_id`로 주문과 추천을 연결하는 부분은 4-3에서.

### 4-3. (선택) 추천 조합 계산을 서버로

**목표**: `POST /api/v1/ai/recommendations`가 답변(인원·예산·맵기·음료 등)과 시간대·날씨로 **조합을 계산해 돌려준다**. 지금은 화면에서 계산하므로 시연에는 필수가 아니다. 1~2단계가 끝난 뒤 여유가 있을 때만 한다.

**테스트 방법**: `user/test_recommendations.py`의 기존 케이스와 같은 입력으로 서버 결과가 같은 조합 id를 돌려준다.

**중요 이론**: 규칙 기반 추천 = 후보 만들기 → 조건(예산·맵기·인원) 필터 → 점수 계산(메뉴 `weight`, 시간대·날씨 가산) → 상위 N개. 점수 규칙이 데이터(`recommendation_rules`)에 있으면 코드를 안 고쳐도 조정된다. 서준의 `menus.weight`(추천 가중치)를 읽는다.

**상세 설명 / TODO**

- [ ] `U/recommendations.py`의 계산 로직을 `B/services/recommend.py`(신규)로 옮기되 화면쪽 원본은 대체 경로로 남긴다.
- [ ] 완료 기준: 같은 입력에서 화면 계산과 서버 계산 결과가 같다는 테스트.

### 4-4. 추천 방식 후보 (담당자가 1개 고름)

질문과 규칙의 구체적인 내용은 담당자가 정한다. 아래는 **방식**만 정리한 후보이다. 어느 방식이든 응답 모양(조합 id 목록, 할인율)은 지금 화면과 같게 유지하고, 4-2의 노출 기록과 연결한다.

| 방식 | 한 줄 설명 | 필요한 질문·규칙 | 장점 | 단점 |
|---|---|---|---|---|
| A. 규칙 기반 점수 (현재 방식) | 답변으로 후보를 거르고 점수(메뉴 `weight`, 시간대·날씨 가산)로 상위 3개를 고른다. `U/recommendations.py`와 같은 구조 | 질문 여러 개 + `recommendation_rules`(짝 `pairings`, 음료 `drinks`, 가산 `hot_themed` 등) | 결과가 항상 같고 설명 가능, 외부 API 없음, 이미 화면에 구현돼 옮기기 쉬움 | 규칙을 사람이 많이 정해야 함 |
| B. 간단 매칭 (질문 2~3개) | 인원·예산·맵기 정도만 묻고, 조건에 맞는 인기 조합을 고정 목록에서 고른다 | 질문 2~3개 + 조합 목록(`pairings`만) | 만들기 쉽고 시연이 빠름, 메뉴가 5개 안팎이어도 동작 | 개인화가 약하고 추천이 단조로움 |
| C. LLM 보조 | 메뉴 목록과 답변을 프롬프트에 넣어 제미나이가 조합을 고르게 한다. 응답은 메뉴 id 목록 JSON으로 받고, 없는 메뉴·예산 초과는 서버가 걸러낸다 | 질문은 자유롭게, 규칙은 최소(`discount_percent`) | 질문·규칙 설계 부담이 적고 자연스러운 설명 가능 | 키·호출 한도·지연 필요, 결과가 매번 달라질 수 있어 실패 시 A나 B로 대체하는 경로가 있어야 함 |

**고르는 기준(제안)**: 시연 안정성이 최우선이면 B에서 시작해 A로 확장하고, C는 A·B 위에 "추천 이유 문구"만 붙이는 선택 기능으로 둔다.

- [x] 담당자가 방식 A(규칙 기반 점수)를 선택했다.
- [x] 고른 방식에 필요한 질문과 규칙 키를 정하고, 시드와 `U/ai_quiz_data.py`·`U/recommendation_data.py`를 같은 내용으로 맞췄다. 규칙이 가리키는 메뉴 id는 기존 `menus` 시드의 id를 사용한다.
- [x] 질문 수는 기존 8단계를 유지해 화면의 단계 표시와 `user/test_ai_quiz.py`를 변경하지 않았다.
