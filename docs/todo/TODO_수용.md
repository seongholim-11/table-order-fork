# 수용 TODO · 관리자 대시보드 · 고객 등급(수신거부 포함)

## 시작 전 공통 규칙

| 항목 | 내용 |
|---|---|
| 경로 표기 | `B/`=`backend/app/` · `A/`=`admin/` · `U/`=`user/` · `T/`=루트 `tests/` · `BT/`=`backend/tests/` |
| 브랜치 | 본 리포를 포크 → 작업마다 `feat/한글설명` 새 브랜치 → PR은 본 리포 `dev`로만. `dev`·`main`에서 바로 작업하지 않는다 |
| 더미 주석처리 (더미 기능만, 구현보다 먼저) | ① 라우터의 `return dummy.xxx(...)` 줄을 `#`으로 주석처리하고 그 아래에 `raise NotImplementedError`를 둔다 ② `B/dummy.py`의 해당 함수와 `DUMMY_ENDPOINTS` 줄을 **같이** 주석처리한다(한쪽만 하면 `test_every_listed_dummy_function_exists`가 실패) ③ 구현·테스트가 끝나면 주석처리해 둔 줄을 지운다 |
| 건드리지 않는 것 | 화면쪽 더미(`U/menu_data.py`, `A/admin_dummy_data.py`)는 서버 없이도 화면이 뜨게 하는 대체 데이터라 지우지 않는다 |
| SQL 위치 | SQL은 `B/stores/`에서만 쓴다. 라우터에는 쓰지 않는다. 테이블 정의 기준은 `docs/db/fbgrowth_schema.sql` |
| 테스트 | 서버 `cd backend && uv run pytest -q` · 화면+통합 `python -m pytest tests -q`. 둘 다 실패 없이 통과해야 PR을 보낸다. 테스트를 skip·삭제해서 통과시키지 않는다(더미 교체 시 `skip` 제거만 허용) |
| 새 테스트 | 공용 파일을 건드리지 말고 본인 이름의 새 파일(예: `BT/test_roulette.py`)에 만든다. `BT/test_dummy_get.py`에서는 본인 기능 줄만 뺀다 |
| 코드 작성 | 수정 파일은 최소로, 기존 코드는 최대한 유지, 새 코드에는 초급 개발자도 읽을 수 있는 한국어 주석(무엇을·왜)을 단다 |
| PR 본문 | 변경 내용 · 테스트 방법 · 테스트 결과 · 미해결 문제(없으면 "없음") |

## 진행 순서

| 순서 | 할 일 | API | 상태 |
|---|---|---|---|
| 1 | 1. 고객 등급 · 수신거부 점검 | `GET /api/admin/customers`, `…/customers/grades`, `…/grades/rules`, `POST …/customers/{id}/opt-out` | 구현 / 부분 구현 |
| 2 | 2. 대시보드 기본 통계 | `GET /api/admin/stats/sales`, `stats/menus/ranking`, `stats/customers`, `stats/ai-recommendations` | 더미 |
| 3 | 3. 대시보드 추가 통계 | `stats/sales/hourly·trends·weekday·tickets`, `stats/tables` | 미구현 |
| 4 | 4. 운영 알림 | `GET /api/admin/alerts` | 미구현 |

**다른 팀원과 겹치는 지점**

| 파일 | 누구와 | 규칙 |
|---|---|---|
| `B/stores/shop_orders.py` | 재현(주문 저장) | 수정하지 않는다. 통계용 읽기 SQL은 `B/stores/stats.py`(신규)에 만든다 |
| `B/services/stats.py` | 성호(챗봇이 "오늘 매출"을 물을 때 호출) | 수용만 수정. 함수 이름이 바뀌면 성호에게 알린다 |
| `B/dummy.py` | 재현·서준·석원 | `dashboard_stats` 함수와 `"GET /admin/api/stats"` 줄만 다룬다. `members()`·`orders()` 더미는 재현의 주문 이력이 쓰므로 재현과 순서를 맞춘다 |
| `A/admin_repository.py` | 모두 | `# ---- 고객 / 주문 / 통계 ----` 구역 안에서만 수정 |

**먼저 알아둘 점**: 통계는 주문 데이터가 있어야 확인할 수 있다. 재현이 주문 저장(`POST /orders`)을 끝내기 전에는 테스트에서 `orders`/`order_items`에 직접 INSERT 해 둔 값(픽스처)으로 확인한다.

---

## 1. 고객 등급 · 수신거부 (구현 / 부분 구현)

### 1-1. `GET /api/admin/customers`, `POST /api/admin/customers/{customerId}/opt-out` (구현됨)

**목표**: 이미 동작한다(`B/routers/admin/members.py`). 고객 목록에 등급이 붙고, 쿼리(`repeat`, `regular`, `dormant`)로 등급 기준을 미리 바꿔 볼 수 있다(저장은 안 됨). 코드를 고치기보다 **다른 기능이 의존하는 계약**이므로 모양을 바꾸지 않는 것이 중요하다.

**테스트 방법**: `BT/test_shop_admin.py::test_members_grades_with_rule_preview_and_profile`(이미 통과 중), `python -m pytest tests/test_admin_data_source.py -q`. 수동: 관리자 > 고객 등급에서 기준을 바꾸면 등급 분포가 바뀐다.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 파생 값은 저장하지 않는다 | 등급은 방문 횟수·마지막 방문일에서 **계산**한다(`B/services/grades.py grade_of`). 기준이 바뀌면 전원이 바로 다시 분류된다 |
| 등급 규칙 | 휴면(마지막 방문 N일 경과) → 단골(방문 ≥ regular) → 재방문(≥ repeat) → 신규 순으로 먼저 맞는 것을 쓴다 |
| 쿼리 파라미터 미리보기 | 저장하지 않고 요청 값으로만 계산해 "이렇게 바꾸면 어떻게 될까"를 보여 준다 |

**흐름**
```
UI(고객 등급 · 기준 조절) → A/views/customers.py → repo.members(rule) (A/admin_repository.py)
 → GET /admin/api/members?repeat&regular&dormant → B/routers/admin/members.py list_members
 → B/stores/members.py all() → DB(members) → B/services/grades.py (등급·연령대 계산)
 → {rule, members:[{id, nickname, grade, age_group,...}]} → pandas 표 → UI 표 + 등급 분포
```

**상세 설명 / TODO**

- [ ] 수신거부 API는 이미 구현(`member_opt_out`)이라 수정 없음. 문자 발송(성호)이 같은 `members.opted_out`을 읽으므로 컬럼 의미를 바꾸지 않는다.
- [ ] 신규 엔드포인트는 같은 파일 `members.py`의 **아래쪽에 추가**만 한다(기존 함수 수정 금지).

### 1-2. `GET /api/admin/customers/grades`, `GET /api/admin/customers/grades/rules` (부분 구현)

**목표**: `grades`는 등급별 고객 수 + 휴면 수, `grades/rules`는 현재 등급 기준(`repeat`, `regular`, `dormant`)을 돌려준다. 지금은 `list_members` 응답 안의 `rule`/`grade`를 화면이 모아서 쓴다. 전용 엔드포인트로 분리한다.

**테스트 방법**: 새 `BT/test_customer_grades.py` — 회원 4명(신규/재방문/단골/휴면 각 1명)을 만들고 `grades`가 `{신규:1, 재방문:1, 단골:1, 휴면:1}` / `rules`가 설정값(`GRADE_REPEAT_VISITS` 등)과 같음 / 쿼리로 기준을 바꾸면 분포가 바뀜 / 인증 없으면 401.

**중요 이론**: 집계(group by)를 SQL로 할지 파이썬으로 할지 — 회원 수가 적은 프로토타입은 `members.all()` 후 파이썬 계산이 단순하다. 기준값 우선순위는 `쿼리 > 설정(.env) > 기본값`(`B/routers/admin/common.py grade_rule`).

**흐름**
```
UI(대시보드 · 등급 카드 / 고객 등급 기준 패널) → A/views/dashboard.py · customers.py → repo (새 메서드)
 → GET /admin/api/customers/grades → B/routers/admin/members.py (새 함수)
 → B/stores/members.py all() → DB(members) → B/services/grades.py grade_of → 등급별 개수 집계
 → {신규, 재방문, 단골, 휴면, dormant_count} → UI 등급 카드
```

**상세 설명 / TODO**

- [ ] `grades`, `grades/rules` 두 함수를 `members.py` 맨 아래에 추가(경로 충돌 주의: `/customers/grades`가 `/customers/{customerId}/…`보다 **먼저** 선언돼야 한다).
- [ ] 경로 문서(v7)는 `/api/admin/customers…`이고 코드는 `/admin/api/members…`이다. 새 경로를 추가하되 기존 `/members`는 유지(별칭)해서 화면과 성호의 문자 기능이 깨지지 않게 한다.
- [ ] 이 두 API는 대시보드 표(2-5)와 같은 함수를 쓴다. 한 번만 구현한다.

---

## 2. 대시보드 기본 통계 (더미)

### 2-1. `GET /api/admin/stats/sales`, `…/stats/menus/ranking`, `…/stats/customers`, `…/stats/ai-recommendations`

**현재 상태**: 서버는 한 엔드포인트 `GET /admin/api/stats`가 고정값(`dummy.dashboard_stats`)을 돌려주고, 화면이 그 값 + 주문/회원 표로 `A/dashboard_stats.py`(pandas)에서 나머지 통계를 계산한다. 먼저 **기존 `/stats`를 실제 계산으로 바꾼 뒤**, 4개 경로는 같은 계산 결과를 나눠 돌려준다.

**목표**: 오늘 주문 수·평균 주문금액·오늘 신규/재방문 고객, 연령대·성별 분포, 인기 메뉴 TOP10, AI 추천 노출 수와 적중률을 DB에서 계산한다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `BT/test_shop_admin.py::test_stats_and_ai_hit_rate`의 `skip` 해제 | 통과 |
| 새 `BT/test_stats.py` | 주문 3건 입력 → `today_orders=3`, `avg_order_amount`가 합계/건수, 어제 주문은 오늘 집계에서 제외(KST), 조합(`combo:`) 주문은 **구성 메뉴 단위**로 인기 메뉴에 셈, `hit_rate = ai_orders / recommendations`(분모 0이면 `null`) |
| `python -m pytest tests/test_dashboard_stats.py tests/test_data_source.py -q` | 화면 쪽 통계가 그대로 통과 |
| 수동 | 대시보드 숫자가 고정값(3건, 30,666원)에서 실제 값으로 바뀐다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 집계 함수 | `COUNT`(건수), `SUM`(합계), `AVG`(평균), `GROUP BY`(묶어서 계산). 대부분의 통계는 이 네 가지다 |
| KST 하루 | DB 시각은 UTC. "오늘"은 KST 0시~24시를 UTC로 바꿔 비교한다 (`B/stores/coupons.py _today_start_utc` 참고) |
| 신규 vs 재방문 | 오늘 주문한 회원을 `grades.grade_of`로 분류해 신규는 신규로, 재방문+단골은 재방문으로 센다 |
| 적중률 | 분자=AI 조합이 포함된 주문 수(`orders.ai_combo`), 분모=추천 노출 수(`recommendation_events`). 정의 문장을 응답 `definition`에 함께 내려 화면에 보여 준다 |
| 0으로 나누기 | 분모가 0이면 `None`을 돌려주고 화면은 "-"로 보여 준다 |

**흐름**
```
UI(대시보드 KPI 카드) → A/views/dashboard.py → repo.stats(rule) (A/admin_repository.py)
 → GET /admin/api/stats → B/routers/admin/stats.py dashboard
 → B/stores/stats.py(신규): 오늘 주문 / 메뉴별 수량 / 추천 노출 수를 SELECT
   + B/stores/members.py all()
 → B/services/stats.py dashboard(orders, members, recommendations, today, rule): 파이썬으로 집계
 → DB(orders, order_items, order_item_components, recommendation_events, members) → 계산 결과 dict
 → UI KPI 카드 · 연령대/성별 막대 · 인기 메뉴 · AI 적중률
```

**상세 설명 / TODO**

- [ ] 더미 주석처리: `B/routers/admin/stats.py`의 `dummy.dashboard_stats()` 줄, `B/dummy.py`의 `dashboard_stats`와 `"GET /admin/api/stats"` 줄.
- [ ] `B/services/stats.py dashboard()`를 파일 안 TODO 순서대로 구현(반환 키는 `dummy.dashboard_stats()`와 같게: `today_orders, avg_order_amount, new_customers, returning_customers, age_groups, genders, popular_menus, ai`).
- [ ] `B/stores/stats.py`(신규): 기간 내 주문 목록(줄·구성 메뉴 포함), 추천 노출 수 조회. `shop_orders.py`는 수정하지 않는다. 재현의 `recommendation_count()`가 준비되면 그것을 써도 된다.
- [ ] 라우터 TODO대로 `today = datetime.now(KST).date()`, `rule = grade_rule(settings)`로 호출.
- [ ] 4개의 세분화 경로(`stats/sales`, `stats/menus/ranking`, `stats/customers`, `stats/ai-recommendations`)는 `dashboard()` 결과의 해당 부분만 잘라 돌려주는 얇은 라우트로 추가한다(계산 중복 금지). 화면은 기존 `/stats`를 계속 써도 된다.
- [ ] `BT/test_dummy_get.py::test_admin_get_dummies`의 stats 줄을 새 테스트로 대체.

---

## 3. 대시보드 추가 통계 (미구현)

### 3-1. `stats/sales/hourly` · `stats/sales/weekday` · `stats/sales/trends` · `stats/sales/tickets` · `stats/tables`

**현재 상태**: 화면이 주문 표를 통째로 받아 `A/dashboard_stats.py`에서 계산한다(`summarize`, `_trend_stats`). 이 계산을 서버 API로 옮기는 작업이다. **시연에는 현재 방식으로도 동작하므로 2번이 끝난 뒤에 진행한다.**

**목표**

| 경로 | 내용 | 참고하는 화면 함수 |
|---|---|---|
| `stats/sales/hourly` | 시간대별 매출 | `summarize`의 `by_hour` |
| `stats/sales/weekday` | 요일별 매출 | `by_weekday` |
| `stats/sales/trends` | 최근 7일 / 마지막 영업일 / 일별(14일) 매출과 증감률 | `_trend_stats` |
| `stats/sales/tickets` | 객단가·금액대 분포·AI 추천 vs 일반 객단가 | `ticket_bands`, `ai_avg_ticket` |
| `stats/tables` | 테이블 회전율·주문 많은 테이블 TOP5 | `turnover_*`, `top_tables` |

**테스트 방법**: 같은 주문 데이터로 **화면 계산(`dashboard_stats.summarize`)과 서버 계산 결과가 같다**는 테스트를 `BT/test_stats.py`에 추가한다(둘 중 하나가 틀리면 바로 드러난다). 빈 데이터면 `empty` 상태(0 또는 빈 객체)를 돌려주고 500이 나지 않는다.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 시간 단위로 묶기 | `GROUP BY` 시(hour) / 요일 / 날짜. DB마다 함수가 달라서(SQLite `strftime`, Postgres `extract`) 프로토타입에서는 파이썬으로 묶는 편이 안전하다 |
| 기준일 | 화면은 "가장 최근 주문일" 기준 최근 30일이다. 같은 규칙을 서버도 따라야 숫자가 일치한다 |
| 회전율 | 하루 주문 건수 / 전체 테이블 수(`store_info.tables`) |
| 증감률 | (이번 − 지난) / 지난. 지난 값이 0이면 `None` |
| 객단가 | 주문 1건당 평균 결제금액 = 매출 / 주문 수 |

**흐름**
```
UI(대시보드 · 시간대/요일 막대, 추이, 테이블 TOP5) → A/views/dashboard.py render_sales_insights·render_trend_insights
 → (현재) repo.orders() 전체 → A/dashboard_stats.py (pandas)
 → (변경) GET /admin/api/stats/sales/hourly 등 → B/routers/admin/stats.py → B/services/stats.py → B/stores/stats.py
 → DB(orders …) → 집계 dict → UI 막대·KPI
```

**상세 설명 / TODO**

- [ ] 라우트는 `B/routers/admin/stats.py`에 추가(수용 단독 파일). 계산 함수는 `B/services/stats.py`에, SQL은 `B/stores/stats.py`에.
- [ ] 화면(`A/dashboard_stats.py`)의 계산 로직을 파이썬 서비스로 옮길 때 **로직을 복사하지 말고 함수 단위로 이식**하고, 화면쪽 원본은 지우지 않는다(`DATA_SOURCE=dummy` 대체 경로).
- [ ] 화면을 서버 값으로 바꿀 때는 `A/views/dashboard.py`와 `A/admin_repository.py` 통계 구역만 수정한다.
- [ ] `stats/tables`의 전체 테이블 수는 `app.state.store_info.get()["tables"]`에서 읽는다.

---

## 4. 운영 알림 (미구현)

### 4-1. `GET /api/admin/alerts`

**현재 상태**: 화면(`A/dashboard_stats.py customer_care`, `menu_alerts`)이 휴면 고객·품절 메뉴 알림을 직접 계산한다. DB에는 `alerts` 테이블이 있다(`kind` = dormant / soldout / other, `acknowledged_at`).

**목표**: 휴면 고객 수·품절 메뉴 같은 운영 알림 목록을 돌려준다. 방식은 "조회할 때 계산해서 돌려주기"로 시작한다(테이블 저장은 확인(읽음) 기능이 필요할 때 추가).

**테스트 방법**: 새 테스트 — 휴면 기준을 넘긴 회원이 있으면 `kind=dormant` 알림이 나온다 / 품절 메뉴(`menus.is_soldout`)가 있으면 `kind=soldout` / 둘 다 없으면 빈 목록 / 인증 없으면 401.

**중요 이론**: 알림을 "저장해 두는 방식"과 "조회 때 계산하는 방식"의 차이 — 저장은 읽음 처리·이력에 좋고 계산은 항상 최신이고 단순하다. 품절 메뉴 정보는 서준의 `menus`를 **읽기만** 한다.

**흐름**
```
UI(대시보드 · 운영 알림 패널) → A/views/dashboard.py render_operations → (새) repo.alerts
 → GET /admin/api/alerts → B/routers/admin/alerts.py(신규)
 → B/stores/members.py all() + 메뉴 품절 조회 → DB(members, menus)
 → B/services/grades.py 로 휴면 판정 → [{kind, title, detail, member_id|menu_id}] → UI 알림 카드
```

**상세 설명 / TODO**

- [ ] `B/routers/admin/alerts.py`(신규)와 등록(성호의 선작업 PR에서 빈 틀로 등록됨. 아직이면 `B/routers/admin/__init__.py`에 한 줄 추가).
- [ ] 메뉴 품절 조회는 서준의 `shop.menus()`를 호출한다(서준 구현 전에는 품절 알림 항목을 비워 두고 TODO 주석을 남긴다).
