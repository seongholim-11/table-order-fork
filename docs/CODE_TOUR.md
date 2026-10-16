# 코드 둘러보기

처음 이 저장소를 연 사람이 "어디에 뭐가 있고, 핵심 코드는 무슨 일을 하는지" 감을 잡기 위한 문서입니다.
작업 순서·규칙(새 API 추가법, 경로 규칙 등)은 `docs/DEVELOPMENT_GUIDE.md`, 실행 방법은 `README.md` 를 보세요.
기능별 동작 흐름(로그인·주문·AI 추천 등)은 `docs/FLOW_USER_ADMIN.md`(손님·사장님 관점)와 `docs/FLOW_DEVELOPER.md`(개발자 관점)를 보세요.

> **현재 상태 (2026-10-16)**: 서버에 실제로 구현된 것은 QR 로그인·문자 발송·고객 목록뿐이고, 나머지 엔드포인트는 `backend/app/dummy.py` 의 더미 응답이며 `services/stats.py`·`stores/shop_*.py` 는 시그니처와 TODO 만 있는 뼈대입니다(`AGENTS.md` 의 "더미 상태" 참고). 3-3·3-4·3-5절의 코드 예시는 이전 구현(커밋 `a8b3d14`)을 기준으로 한 "완성되면 이런 모양" 설명입니다. DB는 지금 SQLite(`app.db`)이고 Supabase 스키마(`docs/DB_SCHEMA.md`)로 옮기는 작업이 남아 있습니다.

## 1. 한 장 요약: 이 프로젝트는 "식당"이다

테이블 오더는 식당 운영과 똑같이 생각하면 쉽습니다.

| 식당 | 이 저장소 | 하는 일 |
|---|---|---|
| 홀(손님이 앉는 곳) 메뉴판·주문 태블릿 | `user/` | 손님이 메뉴를 보고 주문하는 화면 (Streamlit) |
| 사장님 사무실 | `admin/` | 메뉴·주문·고객·문자 마케팅을 관리하는 화면 (Streamlit) |
| 주방 + 창고 + 장부를 한꺼번에 관리하는 매니저 | `backend/` | 모든 데이터를 저장하고 규칙을 지키는 서버 (FastAPI) |
| 홀과 주방 사이를 오가는 서빙 직원 | `shared/api.py` | 화면이 서버에 "주문 넣어 주세요" 하고 전달하는 심부름 코드 |
| 연습용 모형 주방 | 더미 데이터 (`menu_data.py` 등) | 서버가 꺼져 있어도 화면을 돌려 볼 수 있게 하는 가짜 데이터 |

```
 손님 태블릿(user/)            사장님 PC(admin/)
        │                            │
        └──── shared/api.py ─────────┘   ← 서빙 직원 (HTTP 요청)
                     │
              backend/ (FastAPI 서버)
                     │
              app.db (SQLite 파일, 이후 Supabase) ← 장부
```

## 2. 폴더 지도

```
table-order/
├─ backend/      서버 (매니저)
├─ user/         손님 화면
├─ admin/        관리자 화면
├─ shared/       user 와 admin 이 같이 쓰는 서빙 직원 코드
├─ tests/        화면+서버를 묶어서 확인하는 통합 테스트
├─ tools/        보조 스크립트 (더미 데이터 내보내기 등)
├─ docs/         문서
├─ requirements.txt   화면용 패키지 목록
└─ README.md
```

### 2-1. backend/ — 서버(매니저). 4층 건물처럼 나뉜다

```
backend/
├─ main.py                서버 시작 버튼 (한 줄짜리)
└─ app/
   ├─ factory.py          서버를 조립하는 공장
   ├─ core/               ① 설정과 출입 검사
   ├─ routers/            ② 접수 창구 (요청을 받는 곳)
   ├─ services/           ③ 두뇌 (계산·규칙·외부 연동)
   ├─ stores/             ④ 창고 (DB 읽기/쓰기)
   └─ seed/               처음 채워 넣는 기본 메뉴·콘텐츠(JSON)
```

| 층 | 비유 | 파일 예 | 규칙 |
|---|---|---|---|
| `routers/` | 카운터 직원. 주문서를 받아 확인하고 알맞은 곳에 넘긴다 | `user.py`(손님용), `admin/*.py`(관리자용), `auth.py`(로그인) | 직접 창고를 뒤지지(SQL) 않는다 |
| `services/` | 계산·판단하는 두뇌 | `grades.py`(등급 계산), `stats.py`(통계), `sms.py`(문자 발송), `kakao.py`(카카오 로그인) | 화면/DB 를 모르고 계산만 한다 |
| `stores/` | 창고지기. 장부(DB)를 읽고 쓰는 유일한 사람 | `shop_orders.py`, `members.py` … | SQL 은 여기에만 있다 |
| `core/` | 정문 경비실과 설정표 | `settings.py`, `dependencies.py` | 누가 들어올 수 있는지 검사 |

관리자 접수 창구는 기능별로 방이 나뉩니다: `menus / orders / members / stats / sms / content / system`.
창구 한 곳에 몰아 두면 여러 명이 동시에 고칠 때 충돌하기 때문입니다.

### 2-2. user/ — 손님 화면

```
user/
├─ app.py             진입점. "지금 어느 화면을 보여줄까?"만 정한다
├─ views/             화면 한 장을 조립하는 곳 (splash, order, ai)
├─ ui/                여러 화면이 같이 쓰는 조각 (장바구니, 팝업, 룰렛, 로그인)
├─ state/             손님 한 명의 "기억"과 계산 (장바구니, 로그인, 룰렛, 퀴즈…)
├─ user_repository.py 데이터 출입구 (서버냐 더미냐를 여기서만 결정)
├─ server.py          QR 로그인처럼 서버를 직접 부르는 예외 코드
├─ menu_data.py …     더미 데이터 (서버 없이 화면 확인용)
├─ recommendations.py AI 추천 조합 계산
├─ app.css / app_light.css   다크/라이트 테마
└─ assets/menu/       메뉴 사진(webp)
```

비유: `app.py` 는 **홀 매니저**(손님이 어디쯤 있는지 보고 안내), `views/` 는 **테이블 세팅**, `ui/` 는 **재사용 소품**(쟁반·컵), `state/` 는 **주문 메모지**입니다.

> 폴더 이름이 `pages` 가 아니라 `views` 인 이유: Streamlit 은 `pages/` 폴더를 자동으로 새 화면(멀티페이지)으로 인식해 버리기 때문입니다.

### 2-3. admin/ — 관리자 화면

`user/` 와 같은 구조입니다. `app.py`(로그인·사이드바 메뉴), `views/`(대시보드·메뉴·가중치·이벤트·고객·주문·마케팅·로그인), `ui/widgets.py`, `admin_repository.py`(데이터 출입구), `admin_dummy_data.py`(가짜 서버), 그리고 `dashboard_stats.py`·`order_filters.py`·`marketing_ai.py` 같은 계산 모듈이 있습니다.

### 2-4. 두 쪽의 대응표 (같은 역할은 같은 이름)

| 서버(backend) | 화면(user/admin) | 비유 |
|---|---|---|
| `routers/` | `views/` | 손님·직원을 직접 마주하는 창구 |
| `services/` | `state/` | 계산·판단 |
| `stores/` | `shared/api.py`, `*_repository.py` | 데이터를 가져오고 저장하는 통로 |

## 3. 핵심 코드 읽기

### 3-1. 서버 조립 — `backend/app/factory.py`

가게를 여는 순서와 같습니다.

```python
db = Database(settings.database_url)                 # 장부(DB) 한 권을 준비
app.state.members = MemberStore(db)                  # 회원 담당 창고지기
app.state.shop    = ShopStore(db)                    # 메뉴·주문·호출 담당 창고지기
app.state.sms     = SmsService(...)                  # 문자 담당 직원
app.include_router(user.router)                      # 접수 창구를 연다
```

- 모든 창고지기가 **같은 장부(`db`)** 를 나눠 씁니다.
- 라우터는 `request.app.state.shop.add_order(...)` 처럼 불러 씁니다. 필요한 직원을 `app.state` 라는 **직원 명부**에서 꺼내는 셈입니다.
- 운영 환경(`APP_ENV=prod`)에서 비밀번호가 기본값 `change-me` 면 **가게 문을 아예 안 엽니다**(RuntimeError). 열쇠를 안 바꾼 채 영업하지 못하게 하는 안전장치입니다.

### 3-2. 경비실 — `backend/app/core/dependencies.py`

| 함수 | 비유 | 동작 |
|---|---|---|
| `require_admin` | 사장님 사무실 출입증 검사 | `Authorization: Bearer <관리자 토큰>` 이 맞아야 통과, 아니면 401 |
| `current_member` | 회원 전용 라운지 검사 | JWT(회원증)를 풀어 회원을 찾는다. 없으면 401 |
| `optional_member` | 누구나 입장, 회원증이 있으면 혜택 | 회원이면 회원 정보를 붙이고, 아니면 비회원으로 처리 |

관리자 창구(`routers/admin/__init__.py`)는 문 앞에 `require_admin` 을 한 번 걸어 두어 **안쪽 방 전체가 자동으로 보호**됩니다.
JWT 는 `services/tokens.py` 에서 만들고(`issue`) 풀어(`decode`) 보는, 기간이 정해진 **입장 팔찌**입니다.

### 3-3. 장부 — `stores/db.py`, `stores/shop*.py`

- `Database` 는 SQLite 파일(`backend/app.db`) 하나를 여는 **장부 대여 창구**입니다. `run`(쓰기), `all`(여러 줄 읽기), `one`(한 줄 읽기) 세 동작만 있고, 잠금(`Lock`)으로 한 번에 한 명만 쓰게 합니다.
- `ShopStore` 는 메뉴·주문·직원 호출·추천 기록 담당 창고지기 **네 명을 한 사람으로 합친** 것입니다(`MenuMixin + OrderMixin + CallMixin + RecommendationMixin`). 파일은 테이블별로 나뉘어 있어서 팀원이 서로 안 부딪히고, 라우터는 `shop.xxx()` 하나만 알면 됩니다.
- 주문 한 건은 `orders` 테이블의 한 줄입니다. 주문 항목(`lines`)은 JSON 글자로 저장했다가 읽을 때 풀어 줍니다(`_order`). AI 추천 조합(`id` 가 `combo:` 로 시작)이 있으면 `ai_combo=1` 로 표시해 둡니다 → 나중에 "AI 추천 적중률" 통계에 쓰입니다.
- 주의: `CREATE TABLE IF NOT EXISTS` 라서 컬럼을 바꿔도 **이미 있는 `app.db` 는 안 바뀝니다.** 구조를 바꿨다면 `app.db` 를 지우고 서버를 다시 켭니다.

### 3-4. 주문이 들어오는 길 — `backend/app/routers/user.py`

```python
class OrderIn(BaseModel):          # 주문서 양식
    table_no: int = Field(ge=1)    # 테이블 번호는 1 이상
    lines: list[OrderLine] = Field(min_length=1)   # 메뉴가 최소 1개
    total: int = Field(ge=0)

@router.post("/orders", status_code=201)
async def create_order(body: OrderIn, request: Request, member = Depends(optional_member)):
    order = request.app.state.shop.add_order(...)
    return {"no": order["id"], "ai_combo": order["ai_combo"]}
```

- `OrderIn` 은 **주문서 양식**입니다. 수량 0개, 빈 주문 같은 엉터리는 창구에서 자동으로 돌려보냅니다(pydantic 검증).
- 로그인했다면 회원 번호가 같이 저장되고, 안 했다면 비회원 주문으로 저장됩니다(`optional_member`).
- 응답 `201` 은 "접수됐습니다"라는 뜻이고 주문 번호를 돌려줍니다.

같은 파일의 `/api/menus`(메뉴판), `/api/calls`(직원 호출), `/api/recommendations`(추천이 손님에게 보였다는 기록), `/api/members/me`(내 정보)도 같은 방식입니다.

### 3-5. 두뇌 — `services/grades.py`, `services/stats.py`

- `grade_of(member, today, repeat=2, regular=5, dormant=60)`: 단골 판정표입니다. **60일 이상 안 왔으면 휴면 → 5번 이상이면 단골 → 2번 이상이면 재방문 → 나머지는 신규** 순서로 위에서부터 확인합니다. 기준 숫자는 정책이 정해지면 바꿀 수 있도록 인자로 뺐습니다.
- `dashboard(...)`: 사장님 대시보드의 숫자(오늘 주문 수, 평균 주문액, 신규/재방문 손님, 연령·성별, 인기 메뉴 10개, AI 적중률)를 한 번에 계산합니다. AI 조합 주문은 **세트 이름이 아니라 안에 든 메뉴 단위로** 세어서 인기 메뉴가 왜곡되지 않게 합니다.
- AI 적중률 = (AI 조합이 들어간 주문 수) ÷ (추천이 손님에게 노출된 횟수). 정의가 확정 전이라 응답에 "임시 기준"이라고 적혀 있습니다.

### 3-6. 서빙 직원 — `shared/api.py`

화면이 서버에 요청할 때 거치는 **단 하나의 통로**입니다.

- `get / post / put / patch / delete(path, token)` : 요청 보내기.
- 서버가 꺼져 있으면 `ApiUnavailable`(주방 불이 꺼짐), 서버가 거절하면 `ApiError`(주방이 "안 됩니다"라고 답함)를 던집니다. 화면은 이 둘을 구분해서 안내합니다.
- 토큰을 넘기면 `Authorization: Bearer ...` 를 자동으로 붙여 줍니다.
- 테스트에서는 `set_client(TestClient(app))` 로 **진짜 서버를 켜지 않고도** 화면 코드와 서버를 이어서 시험합니다.

### 3-7. 데이터 출입구 — `user/user_repository.py`, `admin/admin_repository.py`

화면 코드는 데이터가 진짜 서버에서 왔는지 연습용 더미인지 **모릅니다.** 출입구에서만 정합니다.

| `DATA_SOURCE` | 뜻 | 비유 |
|---|---|---|
| `dummy` | 코드 안의 가짜 데이터만 | 모형 주방에서 연습 |
| `api` | 서버에서만. 안 닿으면 오류 | 진짜 주방만 인정 |
| `auto`(기본) | 서버가 닿으면 서버, 아니면 더미 | 주방이 쉬면 모형으로 시연 |

- 규칙은 하나: **더미 파일이 곧 응답 명세**입니다. 서버는 더미와 같은 JSON 모양으로 답해야 하고, 그래야 화면을 고치지 않고 가짜→진짜로 바꿀 수 있습니다(`tests/test_admin_data_source.py` 가 모양이 같은지 확인).
- 새 데이터를 서버로 옮길 때는 `ENDPOINTS` 에 경로 추가 → `ApiRepository`(admin 은 `ApiBackend`)에 메서드 추가 → 더미에도 같은 이름 메서드 추가, 이 순서입니다.
- admin 쪽은 한 단계가 더 있습니다: `AdminRepository` 가 서버 JSON 을 화면용 **표(DataFrame)** 로 바꿔 줍니다. 서버 응답 → 표 변환이 한 곳에 모여 있어, 화면은 "표가 오는구나"만 알면 됩니다.

### 3-8. 손님 화면의 심장 — `user/app.py` 와 `user/state/`

`app.py` 의 `main()` 은 사실상 이 순서입니다.

1. `ctx.load()` : 메뉴·카테고리 등 화면 데이터를 한 번 불러옴(실패하면 "직원에게 문의" 안내 후 중단).
2. `init_state()` : 손님 개인의 기억 상자(`st.session_state`)를 준비.
3. `sync_url()` : 현재 화면을 주소창(`?page=order&cat=...`)에 적어 둠 → **새로고침해도 보던 화면으로 복귀**.
4. `page` 값에 따라 `splash`(첫 인사) / `ai_quiz`(AI 질문) / 주문 화면(카테고리 | 메뉴 | 장바구니 3단) 중 하나를 그림.

> Streamlit 은 버튼을 누를 때마다 **파일 전체를 처음부터 다시 실행**합니다. 그래서 장바구니 같은 값은 변수가 아니라 `st.session_state`(사라지지 않는 기억 상자)에 둡니다. 식당으로 치면, 손님이 말을 걸 때마다 직원이 처음부터 서빙을 다시 하는데, 손님의 주문 메모지는 테이블 위에 그대로 놓여 있는 상황입니다.

**`state/session.py`** — 기억 상자 초기화. 눈여겨볼 점:
- `setdefault` : "이미 있으면 그대로 두고 없을 때만 기본값을 넣는다". 다시 실행돼도 기억이 지워지지 않는 비결입니다.
- `table_from_url()` : 태블릿마다 `?table=12` 처럼 **자리표(테이블 번호)** 를 주소로 받습니다. 없거나 이상하면 12번, 범위를 벗어나면 1~전체 테이블 수로 보정합니다.

**`state/cart.py`** — 장바구니 = 계산서.
- 장바구니 한 줄의 열쇠는 `"메뉴id|옵션"`. 같은 메뉴·같은 옵션이면 새 줄이 아니라 **수량만 늘어납니다.**
- 수량이 0 이하가 되면 줄이 삭제됩니다(`cart_change`).
- `cart_total() = 소계 - 룰렛 할인`. 할인은 `소계 × 할인율 // 100 // 10 * 10` 으로, **10원 단위로 내림**합니다(예: 12,340원 × 5% = 617원 → 610원).
- AI 추천 세트는 `components`(세트 안의 메뉴들)를 가진 한 줄로 담기고, 품절 메뉴가 하나라도 있으면 담지 않고 안내(토스트)를 띄웁니다.

**`state/roulette.py`** — 룰렛 = 가게의 뽑기 이벤트.
- 기회는 **로그인한 회원당 하루 1회**(`spins_left`, 한국 시간 기준이며 같은 날 다른 테이블에서도 불가. 서버가 최종 판정).
- `pick_prize_index` : 칸마다 `weight`(관리자 '이벤트'에서 조정)에 **비례해** 당첨 칸을 뽑습니다. 모든 가중치가 0 이면 균등 확률. 사장님이 "꽝을 줄이고 서비스 메뉴를 늘리자"를 화면에서 바로 조정할 수 있는 구조입니다.
- 당첨은 바로 적용되지 않고 **쿠폰함**(`state/coupons.py`, 서버 `coupons`)에 담깁니다. 주문 화면의 "🎟️ 쿠폰함"에서 "사용"을 누르면 `할인`은 `roulette_percent` 에 저장되어(한 번에 하나) 장바구니 계산에 반영되고, `서비스 메뉴`는 0원짜리 항목으로 담깁니다. "취소"로 되돌릴 수 있고, 주문하면 서버가 `used_at` 을 기록합니다.
- 화면이 보여 주는 회전 각도는 당첨 칸이 포인터 아래에 오도록 계산합니다(5바퀴 + 칸 중앙 근처).

**`views/order.py`** — 주문 화면. 메뉴 카드를 만들 때 매운맛 단계가 있는 메뉴는 `group_spicy_variants` 로 한 카드에 묶고, 선택한 단계의 메뉴를 담습니다. 품절이면 버튼이 "품절"로 바뀌며 비활성화됩니다.

**`recommendations.py`** — AI 추천(데모). 인원·예산·매운맛·음료 취향과 이미 주문한 내용, 시간대(심야 22~05시), 사장님이 정한 추천 가중치를 점수로 합산해 메뉴 조합을 고르고, 세트 가격(할인)을 계산합니다. 진짜 AI 모델이 아니라 **규칙 + 점수표** 방식입니다.

### 3-9. 관리자 화면의 진입점 — `admin/app.py`

- 입장: 토큰 확인 후 `ss["owner"]=True`. 개발 편의로 지금은 **토큰 입력을 생략**합니다(`ADMIN_SKIP_TOKEN=0` 이면 다시 켬. 운영 전에 반드시 확인).
- 사이드바 라디오로 메뉴를 고르고 `{"대시보드": page_dashboard, ...}[page](repo)` 한 줄로 해당 화면 함수를 실행합니다. 선택은 주소창(`?page=`)에도 적어 새로고침에 안전합니다.

### 3-10. QR 로그인 — `routers/auth.py` (큰 그림)

손님 태블릿에서 휴대폰으로 로그인하는 흐름은 **"번호표 + 휴대폰 인증"** 과 같습니다.

1. 태블릿이 `POST /api/auth/qr` 로 번호표(토큰·시크릿)와 QR 주소를 받아 화면에 QR 을 띄움.
2. 손님이 휴대폰으로 QR 을 찍으면 `/api/auth/kakao/start` → 카카오 로그인 → `/api/auth/kakao/callback`(키가 없으면 `kakao/mock` 모의 화면).
3. 태블릿은 `GET /api/auth/qr/{secret}` 폴링 또는 `WebSocket /api/auth/ws/{secret}` 으로 "인증 끝났나?"를 확인하고, 끝나면 JWT 를 받아 로그인 상태가 됨.

### 3-11. 문자 마케팅 — `services/sms.py`

사장님이 등급(신규·단골 등)을 골라 문자를 보내는 기능입니다. 주요 안전장치:
- `SMS_DRY_RUN=true`(기본)이면 **실제 발송 없이 기록만** (리허설 모드).
- 야간 발송 제한, 월 한도, 무료수신거부 문구 자동 추가, 수신 동의 회원만 대상.
- 흐름: `preview`(미리보기·검증) → `send`(발송/예약) → `cancel`(예약 취소). 문제가 여러 개면 `{"problems": [...]}` 로 **한 번에 모아서** 알려 줍니다.

## 4. 주문 한 건이 지나가는 길 (전체 그림)

손님이 "담기 → 주문하기"를 누르면:

```
user/ui/dialogs.py confirm_dialog ("주문 확인" 팝업의 [주문하기] 버튼)
   → user_repository.create_order  (서버냐 더미냐 결정)
   → shared/api.py    POST /api/orders  (서빙 직원이 주문서를 들고 감)
   → routers/user.py  create_order      (접수 창구: 양식 검사, 회원 여부 확인)
   → stores/shop_orders.py add_order    (창고지기: orders 테이블에 한 줄 저장)
   ← {"no": 주문번호, "ai_combo": ...}  (접수증)

사장님 PC: admin → GET /admin/api/... → (require_admin 검사) → 주문 이력 / 통계(services/stats.py)
```

## 5. 테스트는 어디에 있나

| 위치 | 확인하는 것 | 비유 |
|---|---|---|
| `backend/tests/` | 서버 API 단독 (로그인, 문자, 더미 응답, 쿠폰 등. 더미 상태인 기능의 테스트는 skip) | 주방 단독 점검 |
| `user/test_*.py` | 장바구니·메뉴 묶기·추천·AI 질문 같은 계산 | 계산기 점검 |
| `tests/` | 화면 ↔ 서버 연결 (QR 로그인 E2E, 관리자 데이터 소스) | 홀과 주방 연결 리허설 |

실행: 저장소 루트에서 `python -m pytest tests`, 서버만은 `cd backend && uv run pytest`.

## 6. 자주 하는 질문

- **"메뉴 가격을 바꾸고 싶어요."** 더미는 `user/menu_data.py`, 서버 기본값은 `backend/app/seed/menu.json`, 운영 중에는 관리자 화면 '메뉴 관리'. (단, 이미 만들어진 `app.db` 는 시드로 덮이지 않으니 필요하면 DB 를 지우세요.)
- **"새 API 를 만들고 싶어요."** 라우터 → 스토어 → 테스트 → 화면 저장소 순서입니다. 자세한 단계는 `docs/DEVELOPMENT_GUIDE.md` 2~3장.
- **"서버 없이 화면만 보고 싶어요."** `DATA_SOURCE=dummy streamlit run user/app.py`.
- **"화면 버튼이 안 먹는 것 같아요."** Streamlit 은 매번 파일을 처음부터 다시 실행합니다. 값이 필요하면 `st.session_state` 에 두었는지, 버튼 처리 뒤 `st.rerun()` 이 필요한지 확인하세요.

## 7. 용어 사전

| 용어 | 쉬운 설명 |
|---|---|
| FastAPI | 서버를 쉽게 만들어 주는 파이썬 도구 (접수 창구 설치 키트) |
| Streamlit | 파이썬만으로 웹 화면을 만드는 도구 |
| API / 엔드포인트 | 서버가 받아주는 주문 창구와 그 주소 (`/api/orders` 등) |
| 라우터 | 주소별로 요청을 알맞은 함수로 보내는 안내판 |
| pydantic | 들어온 데이터가 양식에 맞는지 검사하는 도구 |
| JWT | 로그인했다는 것을 증명하는 기간 한정 입장 팔찌 |
| SQLite | 파일 하나로 된 간단한 데이터베이스 (`app.db`) |
| 더미 | 서버 없이 쓰는 가짜 데이터 |
| 세션 상태 (`st.session_state`) | 화면이 다시 실행돼도 남는 손님별 기억 상자 |
| Mixin | 여러 기능 조각을 한 클래스로 합칠 때 쓰는 부품 (ShopStore 의 네 담당자) |
