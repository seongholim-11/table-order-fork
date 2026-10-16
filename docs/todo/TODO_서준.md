# 서준 TODO · 메뉴 · 카테고리 · 추천 가중치

## 시작 전 공통 규칙

| 항목 | 내용 |
|---|---|
| 경로 표기 | `B/`=`backend/app/` · `A/`=`admin/` · `U/`=`user/` · `T/`=루트 `tests/` · `BT/`=`backend/tests/` |
| 브랜치 | 본 리포를 포크 → 작업마다 `feat/한글설명` 새 브랜치 → PR은 본 리포 `dev`로만. `dev`·`main`에서 바로 작업하지 않는다 |
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
| 1 | 1. 메뉴 저장소 + 손님 메뉴 목록 | `GET /api/v1/menus` | 더미 |
| 2 | 2. 관리자 메뉴 관리 | `GET·POST·PATCH·DELETE /api/v1/owner/menus` | 더미 |
| 3 | 3. 카테고리 | `GET /api/v1/categories`, `POST·PATCH·DELETE /api/v1/owner/categories` | 더미 |
| 4 | 4. 추천 가중치 | `GET·PATCH /api/v1/owner/menus`, `PATCH …/menus/weights` | 더미 |
| 5 | 5. 정리 | `/api/content`, `B/seed/content.json` 삭제 | 마지막 사람이 처리 |

**다른 팀원과 겹치는 지점**

| 파일 | 누구와 | 규칙 |
|---|---|---|
| `B/routers/menus.py` | (서준 전담) | `list_menus`(`/menus`) 함수. 이 파일은 서준만 수정 |
| `B/routers/admin/content.py`, `B/seed/content.json`, `GET /api/content` | 재현(AI 질문·날씨·규칙), 석원(룰렛·직원 호출) | 본인 항목(`categories`)만 옮기고 지운다. 마지막에 모두 옮겨졌는지 확인한 사람(서준)이 파일을 삭제 |
| `B/dummy/` | 재현·수용·석원 | `menu_data.py`(`menus`, `admin_menus`, `menu_saved`)와 `content_data.py`의 `content_item('categories')` 관련 줄만 |
| `B/stores/shop.py` | 재현(주문)·석원(직원 호출) | `ShopStore`는 믹스인 합치는 곳이라 `self.seed_menus()` 한 줄만 건드린다 |
| `A/admin_repository.py` | 모두 | `# ---- 메뉴 ----`, `# ---- 카테고리 CRUD ----`, `# ---- 메뉴 등록 ----` 구역에서만 수정 |
| `U/user_repository.py` | 재현·석원 | `ENDPOINTS["menus"]`·`content`의 `categories` 줄만 |

**다른 사람이 서준의 데이터를 쓴다**: 재현의 주문(`menu_id` 연결), 재현의 추천(`menus.weight`), 석원의 룰렛 서비스 메뉴(`menu_id` FK), 수용의 품절 알림. 그래서 메뉴 저장소(1번)를 **가장 먼저** 끝내고 알려 주는 것이 팀 전체에 도움이 된다.

---

## 0. 개발 흐름 확인 (테스트 버튼) — 가장 먼저

본격적으로 구현하기 전에, 내 PC에서 **포크 → 브랜치 → DB 쓰기·읽기 → 커밋·푸시 → PR** 흐름이 막힘없이 되는지 한 번 확인한다. AI에게 아래 내용을 그대로 시키면 된다.

- [ ] **0-1. 포크·브랜치**: 본 리포를 포크해 내려받고, `dev` 기준으로 `feat/개발흐름-확인-내이름` 같은 새 브랜치를 만든다.
- [ ] **0-2. test 테이블 확인**: Supabase `table-order`에는 `test` 테이블(`id`, `value`, `created_at`, RLS 켜짐)을 **이미 만들어 두었다**. 없다면(다른 프로젝트·새 DB) `docs/db/fbgrowth_test_table.sql`을 SQL Editor에서 실행한다.
- [ ] **0-3. 테스트 버튼 만들기** (내 브랜치에서만. `DEV_TEST_BUTTON=1`일 때만 보이는 **개발 전용** 버튼):
  - 위치: **손님 시작 화면(룰렛이 있는 화면)**(`U/views/splash.py`)의 "📱 로그인" 버튼(`key="login_open"`) 옆. 화면 코드는 `api`를 직접 부르지 말고 `U/user_repository.py`를 통해서만 서버를 부른다.
  - 서버: `POST /api/dev/db-test`(`B/routers/dev.py` 신규, SQL은 `B/stores/`의 신규 저장소에). `test` 테이블에 임의 값을 INSERT → 같은 행을 다시 SELECT → 값이 같으면 `{"result": 1}`, 아니면 `{"result": 0}`. 확인용 행은 지운다.
  - 서버 `.env`에 `DEV_TEST_BUTTON=true`일 때만 이 경로를 열고, 꺼져 있으면 404. 화면 쪽은 환경변수 `DEV_TEST_BUTTON=1`일 때만 버튼을 보인다. `.env.example`에도 적는다.
  - 화면에는 결과 `1`(정상) 또는 실패 이유를 표시한다.
- [ ] **0-4. 테스트**: `cd backend && uv run pytest -q`와 `python -m pytest tests -q`가 통과하는지 확인한다.
- [ ] **0-5. 버튼 확인**: 서버와 손님 화면(`streamlit run user/app.py`)을 `DEV_TEST_BUTTON`을 켠 채 실행하고, 버튼을 눌러 `1`이 나오는지 본다.
- [ ] **0-6. 커밋·푸시·PR**: 한국어 커밋 메시지로 커밋하고 내 포크에 푸시한 뒤, **본 리포 `dev`로 PR**을 보낸다(본문: 변경 내용·테스트 방법·테스트 결과·미해결 문제).
- [ ] **0-7. 마무리**: 이 PR은 흐름 확인용이므로 **머지하지 않고 PR만 닫는다**(버튼 코드는 `dev`에 들어가지 않는다). 확인이 끝나면 위 항목을 모두 `[x]`로 바꾸고 맨 위 진행 순서 표의 0번 상태를 "완료"로 고친다. 이 체크 변경은 첫 실제 기능 PR에 함께 넣는다.

> 이 단계에서 막히면(포크·푸시·DB 연결·PR 권한 등) 구현을 시작하지 말고 먼저 팀에 알린다. 실제 문제 기록은 `docs/TODO_충돌_오류.md`에 남긴다.

---

## 1. 메뉴 저장소 + 손님 메뉴 목록 (더미)

### 1-1. `GET /api/v1/menus`

**목표**: 손님 주문 화면의 메뉴 목록(품절 여부·매운맛 단계 포함, 품절도 전부 내려주고 `soldout`로 표시)을 `menus` 테이블에서 읽는다. 먼저 `B/stores/shop_menus.py`(저장소)를 구현하는 작업이다 — 2~4번이 모두 이 저장소를 쓴다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `BT/test_shop_admin.py::test_menu_seeded_and_admin_edits_reach_users`의 `skip` 해제 | 서버 시작 시 `B/seed/menu.json`(60개)이 `menus`에 채워지고 `GET /api/menus`가 60개를 돌려준다 |
| `BT/test_dummy_get.py::test_user_get_dummies`의 menus 줄 | 새 테스트(`BT/test_menus.py`)로 대체 |
| 응답 모양 | 각 메뉴에 `id, cat, name, desc, price, emoji, tags, soldout, spicy, weight, set_ok, image_url`가 있다 |
| 수동 | 손님 주문 화면에서 카테고리를 눌러 메뉴 카드가 보인다. 관리자에서 품절 처리 → 10초 안에 손님 화면에 "품절" 표시 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 시드(seed) 데이터 | 테이블이 비어 있을 때만 JSON 파일로 초기 데이터를 채운다. 이미 있으면 건드리지 않아야 재시작해도 관리자 수정이 유지된다 |
| 이름 변환 | DB 컬럼(`category_id`, `description`, `is_soldout`)과 화면이 쓰는 키(`cat`, `desc`, `soldout`)가 다르다. 변환은 저장소에서만 한다 |
| 목록 컬럼 | `tags`는 DB에서 목록(배열)이다. SQLite 호환 구조에서는 JSON 문자열이라 `db.from_list`/`db.to_list`로 변환한다 |
| UPSERT | `INSERT … ON CONFLICT(id) DO UPDATE`: 있으면 수정, 없으면 추가를 한 문장으로. 수정할 땐 보낸 필드만 바꾼다 |
| 캐시 | 손님 화면은 서버 값을 10초 캐시한다(`st.cache_data(ttl=10)`). 그래서 관리자 수정이 최대 10초 늦게 보인다(오류 아님) |

**흐름**
```
UI(주문 화면 · 카테고리 탭 · 메뉴 카드) → U/views/order.py → ctx.MENU ← U/user_repository.py load_content
 → GET /api/menus → B/routers/menus.py list_menus
 → B/stores/shop_menus.py menus() → DB(menus 60행, sort_order 순)
 → 컬럼 이름 변환(cat/desc/soldout) → [{id, cat, name, desc, price, soldout, ...}] → UI 메뉴 카드
```

**상세 설명 / TODO**

- [ ] 더미 주석처리: `B/routers/menus.py list_menus`의 `dummy.menus()` 줄, `B/dummy/menu_data.py`의 `menus()`와 `"GET /api/menus"` 줄. (`admin_menus()`와 `menu_saved()`가 `menus()`를 쓰므로 2번과 순서를 같이 맞춘다 → 1·2번을 같은 PR로 묶는 것을 추천)
- [ ] `B/stores/shop_menus.py` 구현: `seed_menus`, `menus`, `menu`, `save_menu`, `delete_menu`(파일 안 TODO 순서대로). 컬럼 목록은 `MENU_FIELDS`.
- [ ] `B/stores/shop.py`의 `# TODO: 구현 후 self.seed_menus() 를 불러…` 주석 줄을 실제 호출로 바꾼다(그 한 줄만).
- [ ] 추가한 메뉴 id는 문자열이다(`c1`, `m3fa2b1`). 숫자로 가정하지 않는다.
- [ ] 끝나면 재현·석원·수용에게 "`shop.menus()`/`menu(id)` 쓸 수 있어요"라고 알린다.

---

## 2. 관리자 메뉴 관리 (더미)

### 2-1. `GET /api/v1/owner/menus`, `POST /api/v1/owner/menus`, `PATCH /api/v1/owner/menus/{menuId}`, `DELETE /api/v1/owner/menus/{menuId}`

**현재 상태**: 코드는 `GET /admin/api/menus`(메뉴 + 카테고리), `PUT /admin/api/menus/{id}`(없으면 등록, 있으면 수정), `DELETE /admin/api/menus/{id}`이다. 문서 경로(POST/PATCH)와 모양이 다르므로 **먼저 현재 PUT 방식으로 구현**하고, POST/PATCH는 같은 함수를 부르는 얇은 라우트로 추가한다(화면은 PUT을 계속 쓴다).

**목표**: 사장님이 메뉴를 등록·수정(가격·설명·이미지·판매 여부·매운맛·세트 가능)·삭제하면 DB에 저장되고 손님 화면에 반영된다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `BT/test_shop_admin.py::test_admin_menu_create_delete_and_validation`의 `skip` 해제 | 통과 |
| 새 `BT/test_menus.py` | 신규 등록은 `name`·`cat`·`price` 필수(없으면 422), 없는 카테고리면 422, 수정은 보낸 필드만 바뀜, 삭제하면 `GET`에서 사라지고 없는 id 삭제는 404, 인증 없으면 401, `weight`가 0~100 밖이면 422 |
| `python -m pytest tests/test_admin_menu_page.py tests/test_data_source.py -q` | 화면 테스트의 `skip` 중 이 기능 때문인 것을 해제하고 통과 |
| 수동 | 관리자 > 메뉴 관리에서 메뉴 추가 → 표 저장 → 손님 화면에 새 메뉴가 보인다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 요청 모델 검증(Pydantic) | `MenuIn`이 타입·범위를 자동 검사하고 어기면 422를 돌려준다. 검증 코드는 이미 있으니 건드리지 않는다 |
| 부분 수정 | `body.model_dump(exclude_none=True)`로 "보낸 것만" 꺼내 UPDATE한다. 안 보낸 필드를 null로 덮어쓰면 데이터가 사라진다 |
| 가상 카테고리 | `ai`, `best`는 손님 화면용 가짜 카테고리라 메뉴를 넣을 수 없다(`NON_MENU_CATEGORIES`) |
| 멱등한 PUT | 같은 요청을 두 번 보내도 결과가 같다. 새 id를 화면이 만들어 보내는(`m` + 6자리) 구조와 잘 맞는다 |
| 삭제와 FK | 주문 줄(`order_items.menu_id`)과 룰렛 서비스 칸(`roulette_prizes.menu_id`)이 메뉴를 참조한다. 주문 쪽은 지워져도 이름 사본이 남지만, 룰렛 칸에 쓰는 메뉴는 삭제가 막힐 수 있다 → 409 안내 메시지 고려 |

**흐름**
```
UI(메뉴 관리 · 표 편집 후 저장) → A/views/menu.py save_menu_changes → repo.save_menus (A/admin_repository.py)
 → PUT /admin/api/menus/{id} {name, cat, price, desc, soldout, spicy, weight, set_ok…}
 → B/routers/admin/menus.py save_menu (MenuIn 검증, 카테고리 확인)
 → B/stores/shop_menus.py save_menu (UPSERT) → DB(menus) → 저장된 메뉴 dict
 → 화면이 표를 다시 그림 → (손님) 10초 캐시 뒤 GET /api/menus 로 반영
```

**상세 설명 / TODO**

- [ ] 더미 주석처리: `B/routers/admin/menus.py`의 `dummy.admin_menus()`, `dummy.menu_saved(...)`, 삭제의 더미 줄과 `menu_categories()` 안의 `dummy.content_item("categories")`, `B/dummy/menu_data.py`의 `admin_menus`·`menu_saved`와 `ENDPOINTS`의 `"GET /admin/api/menus"`, `"PUT /admin/api/menus/{menu_id}"` 줄.
- [ ] 라우터의 TODO 순서대로: ① `cat`이 `menu_categories()`에 없으면 422 ② 없는 id면 등록(필수값 검사), 있으면 보낸 필드만 수정 `shop.save_menu(menu_id, fields)` ③ 삭제는 `shop.delete_menu`가 `False`면 404.
- [ ] `menu_categories()`는 3번(카테고리 저장소)이 끝나면 `categories` 테이블을 읽게 바꾼다. 그 전에는 `B/seed/content.json`의 카테고리를 그대로 읽는 임시 코드로 둔다(TODO 주석 표시).
- [ ] 응답 `{categories, menus}` 모양을 바꾸지 않는다(화면 `A/admin_repository.py`가 이 모양을 기대).
- [ ] 문서 경로용 별칭(`POST /v1/owner/menus`, `PATCH /v1/owner/menus/{menuId}`)은 `save_menu`를 재사용해 추가한다.

---

## 3. 카테고리 (더미)

### 3-1. `GET /api/v1/categories`, `POST·PATCH·DELETE /api/v1/owner/categories`

**현재 상태**: 카테고리는 `B/seed/content.json`의 한 항목이고, 관리자가 바꾸면 **목록 전체를 통째로 교체**(`PUT /admin/api/content/categories`)한다. 저장은 되지 않는 더미다. 카테고리 저장소 파일(`stores/…`)은 아직 없다.

**목표**: `categories` 테이블에서 읽고, 추가·수정·삭제 API를 제공한다. 삭제는 그 카테고리에 메뉴가 있으면 불가(409). 가상 카테고리(`ai`, `best`)는 수정·삭제 불가.

**테스트 방법**: 새 `BT/test_categories.py` — 목록 순서(`sort_order`)와 메뉴 개수(관리자용), 이름 중복 거부, 메뉴가 있는 카테고리 삭제는 409, 빈 카테고리 삭제 성공, `ai`/`best` 삭제 거부. 화면: `tests/test_admin_menu_page.py`(카테고리 추가·수정·삭제·중복 이름 케이스)가 그대로 통과.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 참조 무결성 | `menus.category_id → categories.id`. 메뉴가 있는 카테고리를 지우면 DB가 막는다(`on delete restrict`). 에러를 잡아 사람이 읽는 메시지(409)로 바꾼다 |
| 색 두 개 | 카드 배경 그라데이션이라 `color_from`/`color_to` 두 값을 저장한다. 화면은 `colors:[c1, c2]` 리스트로 다룬다 |
| 통째 교체 vs 개별 변경 | 지금 화면은 목록 전체를 보내는 방식이라, 개별 API(POST/PATCH/DELETE)로 바꾸면 화면 쪽 `save_categories`도 바꿔야 한다. 둘을 동시에 지원하는 기간을 둔다 |
| 표시 순서 | `sort_order`로 정렬한다. 새 카테고리는 `MAX+1` |

**흐름**
```
UI(메뉴 관리 · 왼쪽 카테고리 패널 · 추가/수정/삭제) → A/views/menu.py render_category_panel → repo.add_category 등 (A/admin_repository.py)
 → (현재) PUT /admin/api/content/categories (전체 교체) → (변경) POST·PATCH·DELETE /admin/api/…/categories
 → B/routers/admin/categories.py(신규) → B/stores/categories.py(신규) → DB(categories)
 → 결과 → 화면이 카테고리 패널을 다시 그림 → (손님) GET /api/content 의 categories ← 같은 테이블에서
```

**상세 설명 / TODO**

- [ ] `B/stores/categories.py`(신규): `list`, `add`, `update`, `delete`, 비어 있을 때 `content.json`의 카테고리로 시드. `ai`, `best`는 `is_virtual=true`.
- [ ] `B/routers/admin/categories.py`(신규) + 손님용 `GET /api/v1/categories`. 손님 응답은 지금 화면이 받는 모양 `[{id, icon, name, colors:[c1,c2]}]`을 유지한다.
- [ ] 손님 화면은 `/api/content`의 `categories`를 쓰므로(`U/user_repository.py _fetch_content`), 새 경로를 쓰도록 **본인 줄만** 바꾼다.
- [ ] `A/admin_repository.py`: 현재 `save_categories`(전체 교체)를 개별 호출로 바꿀 때 `CategoryError` 메시지(이름 중복·빈 이름·메뉴 남음)가 그대로 화면에 나오게 유지한다.
- [ ] 완료되면 `B/seed/content.json`의 `categories` 키를 지운다(다른 키는 재현·석원이 지움). `content.py`·`content.json`에 남은 키가 없으면 파일을 삭제하고 `B/routers/admin/__init__.py`의 등록 줄도 지운다.

---

## 4. 추천 가중치 (더미)

### 4-1. `GET /api/v1/owner/menus` (가중치 조회), `PATCH /api/v1/owner/menus/{menuId}` (단건 변경), `PATCH /api/v1/owner/menus/weights` (일괄 저장)

**목표**: 관리자 > 추천 가중치 화면에서 메뉴별 가중치(0~100, 기본 50)를 보고 바꿔 저장한다. 이 값은 AI 추천(재현)과 AI 마케팅 추천(석원)이 읽는다.

**테스트 방법**: 새 `BT/test_menus.py`에 추가 — 일괄 저장 후 `GET`에서 값이 바뀜 / 범위(0~100) 밖이면 422 / 없는 메뉴 id가 섞이면 전체를 거부(부분 저장 금지) / `weights` 경로가 `{menuId}`로 잘못 해석되지 않음. 화면: `tests/test_admin_menu_page.py`의 가중치 관련 케이스.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 라우트 선언 순서 | FastAPI는 위에서부터 경로를 맞춰 본다. `PATCH /menus/weights`를 `PATCH /menus/{menu_id}`보다 **먼저** 선언하지 않으면 `weights`가 메뉴 id로 처리된다 |
| 일괄 저장은 원자적으로 | 여러 메뉴를 한 번에 바꿀 때 하나라도 실패하면 전부 취소(트랜잭션)해야 화면과 DB가 어긋나지 않는다 |
| 가중치의 의미 | 추천 점수 계산에서 곱해지는 값이다. 0이면 추천에서 사실상 제외, 100이면 최우선 |

**흐름**
```
UI(추천 가중치 · 슬라이더 조절 · 저장) → A/views/weights.py render_weight_panel → repo.save_menus
 → (변경) PATCH /admin/api/menus/weights {items:[{id, weight}]}
 → B/routers/admin/menus.py (weights 라우트를 {menu_id} 보다 위에 선언)
 → B/stores/shop_menus.py (여러 행 UPDATE, 한 트랜잭션) → DB(menus.weight)
 → 저장된 목록 → UI 슬라이더 값 갱신
```

**상세 설명 / TODO**

- [ ] 현재 화면은 가중치도 메뉴 저장(`PUT /menus/{id}`)과 같은 경로로 보낸다. 일괄 라우트를 추가해도 기존 PUT은 유지한다.
- [ ] `shop_menus.py`에 `save_weights(items)` 추가(서준 파일). 요청 모델은 `B/routers/admin/menus.py`에 `WeightsIn`으로 추가.
- [ ] 알림: 가중치를 바꾸면 손님 AI 추천 결과가 달라진다. 재현에게 `menus.weight` 컬럼을 읽는다는 점을 확인해 둔다.

---

## 5. 정리 (마지막)

- [ ] `B/seed/content.json`에 남은 키가 없으면 `B/routers/admin/content.py`, `GET /api/content`, `dummy.content()`/`content_item()`을 삭제하고 `U/user_repository.py _fetch_content`가 새 경로만 쓰는지 확인한다.
- [ ] `B/dummy/`의 `*_data.py`가 모두 비면(그때 `dummy/` 폴더 자체를 지운다) `AGENTS.md`의 "더미 상태" 섹션을 삭제한다(PR에 AGENTS.md 변경 포함, 팀에 알림).
- [ ] `docs/DB_설계.md`와 `docs/db/*.sql`을 바꿨다면 두 문서를 같이 고치고 팀에 알린다.
