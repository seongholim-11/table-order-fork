# Table Order

FastAPI 서버 + 사용자 페이지 + 관리자 페이지를 한 저장소에서 관리하는 모노레포입니다. (역전할머니맥주 홍대점 시연용)

> **현재 상태**: **QR 로그인**, **문자 발송(솔라피)**, **고객 목록·등급·수신거부**, **대시보드 기본·추가 통계**, **메뉴 품절 조회**, **손님 메뉴 목록**이 실제 DB와 연동됩니다. 손님 메뉴 목록은 `GET /api/menus`에서 `menus` 테이블을 읽고, 비어 있으면 기본 메뉴를 채웁니다. 아직 더미인 API도 남아 있으며 `backend/app/dummy/`의 `DUMMY_ENDPOINTS`와 라우터의 `dummy.` 호출로 구분합니다. 담당별 최신 진행 상태는 `docs/todo/TODO_*.md`를 확인하세요.

```
backend/   FastAPI 서버 (app factory 구조: core / routers / services / stores)
user/      사용자(손님) Streamlit 페이지
admin/     관리자 Streamlit 페이지
shared/    두 페이지가 같이 쓰는 API 호출 코드
```

### 화면 코드 구조 (user·admin 공통 규칙)

`app.py` 는 진입점(로그인·메뉴 선택·화면 연결)만 맡고, 화면 코드는 역할별 폴더로 나눕니다.
폴더 이름이 `pages` 가 아니라 `views` 인 이유는 Streamlit 이 `pages/` 폴더를 자동 멀티페이지로 인식하기 때문입니다.

| 폴더 | 역할 | 백엔드의 대응 계층 |
|---|---|---|
| `views/` | 화면 하나를 조립하는 함수 (`page_*`, `render_*`) | `routers/` |
| `ui/` | 여러 화면이 같이 쓰는 UI 조각·다이얼로그 | - |
| `state/` | `st.session_state` 조작과 계산 (장바구니·로그인·퀴즈 등), `context.py` 는 매장 데이터 | `services/` |
| `shared/api.py`, `*_repository.py` | 서버/더미 데이터 호출 | `stores/` |

- `admin/`: `views/`(대시보드·메뉴·가중치·이벤트·고객·주문·마케팅·로그인), `ui/widgets.py`
- `user/`: `views/`(splash·order·ai), `ui/`(common·cart·dialogs·login·roulette), `state/`(session·cart·login·roulette·quiz·context)
- 새 모듈은 저장소 루트 기준으로 `from user.state.cart import ...`, `from admin.ui.widgets import ...` 처럼 import 합니다. (예전부터 있는 `admin_repository`, `user_repository`, `server` 등 최상위 모듈은 폴더 이름 없이 import 합니다. 자세한 규칙은 `docs/개발_가이드.md`)
- 서버 관리자 API 는 `backend/app/routers/admin/` 안에 기능별 파일(menus·orders·members·stats·sms·content·system)로 나뉘어 있습니다.

### 수용 담당 1~4번 완료 확인 (2026-10-17)

- [x] **1. 고객 등급·수신거부**: 고객 화면에서 신규·재방문·단골·휴면으로 표시하며, 휴면 기본 기준은 마지막 방문 후 **30일 이상**입니다. 등급 기준 미리보기는 회원 기록이나 기본 기준을 저장하지 않습니다. 오늘 주문한 단골의 방문 기록과 확인 가능한 메뉴 취향은 고객 목록의 별도 메모 없이 **마케팅 > AI 추천**에서 안내합니다.
- [x] **2. 대시보드 기본 통계**: 오늘 주문 수·평균 주문금액·신규/재방문 고객, 인기 메뉴·AI 지표를 실제 DB에서 계산합니다.
- [x] **3. 대시보드 추가 통계**: 시간대·요일·기간별 매출, 증감률, 객단가·금액대 분포, 테이블 회전율을 실제 DB에서 계산합니다. 증감률 상승은 빨강, 하락은 파랑입니다.
- [x] **4. 메뉴 품절 조회**: `/admin/api/alerts`가 DB의 품절 메뉴와 전체 판매 수량 TOP10에 포함되는 품절 메뉴를 반환합니다. 품절이 없으면 빈 목록이며, 인증 없는 요청은 401입니다. 재입고 후 새로고침하면 목록에서 제외됩니다.

4번은 현재 합의된 **메뉴 품절 조회·중복 고객 카드 제외** 범위입니다. 휴면 고객 정보는 고객 등급 화면에 남기며, 품절을 직접 바꾸는 메뉴 등록·수정 기능은 메뉴 담당 영역입니다. 알림 이력 저장·읽음 처리는 이번 범위에 포함하지 않습니다.

**마케팅 > AI 추천의 단골 손님 응대 제안**은 기존 추천 문구·순서·추천 4개·재추천 순환을 그대로 두고, 그 아래에 **‘오늘은 이런 멘트 어떠세요?’ 안내로 조건에 맞는 손님을 인원 제한 없이 모두 표시**합니다. DB에서 단골로 분류된 방문 5회 이상 고객의 오늘 주문이 확인되면, 선호 메뉴 유무와 관계없이 로그인 기록 기준 N번째 방문과 오늘 주문 메뉴를 알려줍니다. 오늘을 제외한 과거 주문일이 5일 이상이고 같은 안주를 고른 날의 비율이 **80% 이상**일 때만 메뉴 취향을 추가로 설명합니다. 평소 메뉴도 함께 주문했다면 다른 메뉴만 골랐다고 말하지 않고, 현재 품절 상태로 손님의 선택 이유를 추측하지 않습니다. 확인된 사실과 상황별 부드러운 멘트 예시를 구분해 제공하며, 사장님이 말투에 맞게 바꿀 수 있습니다. `/admin/api/marketing/regular-preferences`로 실제 DB를 읽으며, 한 날의 추가 주문·많은 수량으로 비율을 부풀리지 않습니다. 무료 서비스·주류·음료는 선호 안주 근거에서 제외하지만, 오늘 음료만 주문한 단골도 방문 안내 대상입니다. 추가 조회가 실패해도 기존 추천은 유지됩니다.

DB에 `[예시]` 단골 3명과 주문 33건을 구분해 추가했습니다. 세 손님 모두 과거 10일 중 8일 같은 안주를 고른 이력이며, 오늘은 각각 먹태구이 → 골뱅이 소면 무침 (순한맛), 계란말이 → 해물파전, 해물파전 → 먹태구이를 주문한 상황입니다. 이 실제 주문을 근거로 음식을 전달할 때 쓸 멘트를 함께 확인할 수 있습니다. 연락처·문자 수신 동의 없이 생성했으며 예시 주문도 매출 통계에 포함됩니다. `backend/.venv/Scripts/python.exe tools/seed_regular_preferences.py`를 다시 실행해도 같은 예시를 중복 생성하지 않습니다. 요청에 따라 이번 예시만 복원 후 재추가했으며 기존 고객 41명·주문 133건은 변경되지 않았습니다. 예시만 다시 구성할 때는 이 도구의 `--reset-examples` 옵션을 사용하며, 전체 작업 실패 시 복원 전 상태로 되돌아갑니다.

단골 응대 제안은 AI 추천 화면 진입이나 재추천 등 화면 갱신 시 DB를 다시 조회합니다. 주문 직후 자동 알림·자동 갱신과 퇴점 시 숨김은 구현하지 않았으며, 오늘 주문이 있으면 당일에는 안내가 남을 수 있습니다.

PR 전 최신 `upstream/dev`를 반영한 전체 테스트는 서버 **179 passed, 9 skipped**, 화면·통합 **124 passed, 12 skipped**입니다. 단골 10명이 주문한 경우 모두 표시하는 테스트와 실제 Supabase/API 대조, 실제 API를 쓰는 관리자 화면을 확인했습니다. 0번 개발 흐름 확인·PR 절차의 미체크 항목은 별도이며, 자세한 근거와 남은 절차는 [수용 TODO](docs/todo/TODO_수용.md)를 참고하세요.

## 실행

```bash
# 서버 (http://127.0.0.1:8000/docs)
cd backend
cp .env.example .env
uv sync
uv run fastapi dev main.py

# 페이지 (저장소 루트에서, 서버가 켜져 있어야 QR 로그인·문자 발송이 동작)
uv venv .venv
source .venv/Scripts/activate   # macOS/Linux 는 source .venv/bin/activate
uv pip install -r requirements.txt
streamlit run user/app.py --server.port 8501    # 사용자 (?table=12 로 테이블 지정)
streamlit run admin/app.py --server.port 8502   # 관리자 (APP_ENV=dev 면 토큰 입력 생략. 끄려면 ADMIN_SKIP_TOKEN=0, 토큰은 ADMIN_TOKEN)
```

- 휴대폰으로 QR 로그인을 시험하려면 `backend/.env` 의 `PUBLIC_BASE_URL` 을 서버 PC 주소(예: `http://192.168.0.10:8000`)로 두고 `--host 0.0.0.0` 으로 실행하세요. 카카오 키가 없으면 모의 로그인 화면이 열립니다.
- 문자 발송은 `SMS_DRY_RUN=true`(기본)이면 실제 전송 없이 기록만 남깁니다.
- 문자는 솔라피로 발송하며 `SOLAPI_API_KEY`·`SOLAPI_API_SECRET`·`SOLAPI_SENDER_NUMBER`·`SMS_OPT_OUT_NUMBER`(무료수신거부 번호)가 필요합니다.
- 문자 발송 테스트(관리자 토큰 필수, 회원·동의 조건 없이 번호 1건 즉시 발송. 월 한도·야간 제한은 적용, 본문 앞에 `[테스트]` 가 붙음):
  ```bash
  curl -X POST http://localhost:8000/admin/api/sms/test \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d '{"phone": "010-1234-5678", "body": "테스트 문자입니다"}'
  # → {"ok": true, "dry_run": true, "type": "SMS", "request_id": "dryrun-...", "to": "01012345678"}
  ```
  `SMS_DRY_RUN=true` 면 실제 전송 없이 기록만, 실패 시 409 + `{"detail": {"ok": false, "problems": [...]}}`.
- QR 로그인·솔라피 문자 구현 기준과 카카오/Supabase 로그인 설정 가이드: `docs/정식_구현_계획.md`
- 팀원용 개발 가이드(새 API 추가 순서, 경로 규칙, DB 스키마 변경 규칙): `docs/개발_가이드.md`
- 핵심 기능 플로우(로그인·룰렛·쿠폰함·주문·AI 추천·직원 호출·문자): 손님·사장님 관점 `docs/기능흐름_손님_관리자.md`, 개발자 관점 `docs/기능흐름_개발자.md`
- DB 설계(테이블·결정 사항·API 대응, 실행용 SQL은 `docs/db/fbgrowth_schema.sql`): `docs/DB_설계.md`
- 코드 둘러보기(폴더 지도·핵심 코드 설명): `docs/코드_둘러보기.md`
- TODO 구현 중 예상 충돌·오류와 해결 방법: `docs/TODO_충돌_오류.md`
- 담당자별 TODO(성호·재현·수용·서준·석원): `docs/todo/TODO_*.md` (끝낸 항목은 `- [x]`로 체크해 PR에 포함)
- API 경로 기준(v7)과 담당 분배표: `docs/api/`
- 팀원 공지(문서 위치·작업 순서 요약): `docs/팀_공지.md`
- 협업 규칙: 조직 리포를 **포크**해서 내 포크의 `main` 에서 개발하고, PR 은 본 리포의 **`dev`** 로만 보냅니다(`main` 은 SEONGHO 가 확인 후 머지). 커밋·PR 메시지 규칙은 `AGENTS.md` 의 "Git 규칙".

## Streamlit Community Cloud 배포 (user·admin 각각)

같은 저장소에서 앱 두 개를 따로 만듭니다. <https://share.streamlit.io> → **Create app** → *Deploy a public app from GitHub* 에서 두 번 반복하세요.

| 앱 | Repository | Branch | Main file path | 권장 URL |
|---|---|---|---|---|
| 사용자 | `aio-03-p1-team1/table-order` (또는 배포용 포크) | `main` | `user/app.py` | `…-user.streamlit.app` |
| 관리자 | `aio-03-p1-team1/table-order` (또는 배포용 포크) | `main` | `admin/app.py` | `…-admin.streamlit.app` |

- 의존성은 루트 `requirements.txt`, 테마는 루트 `.streamlit/config.toml` 을 두 앱이 함께 씁니다. Python 버전은 Advanced settings 에서 3.11 이상을 고르세요.
- Advanced settings → **Secrets** (TOML, 최상위 키는 환경 변수로도 읽힙니다):
  - 둘 다 더미로만 시연: `DATA_SOURCE = "dummy"`
  - 관리자 더미 로그인 토큰 바꾸기: `ADMIN_TOKEN = "원하는-비밀번호"` (기본값 `change-me` 는 공개 배포 시 반드시 변경)
  - 실제 백엔드 연결: `DATA_SOURCE = "api"` 와 `API_URL = "https://백엔드-주소"` (FastAPI 서버는 Streamlit Cloud 에서 돌릴 수 없으니 Render/Fly.io 등에 따로 배포하고, 그 `CORS_ORIGINS`·`PUBLIC_BASE_URL` 에 두 앱 주소를 넣으세요)
- `DATA_SOURCE=auto`(기본)에서 `127.0.0.1` 서버는 클라우드에서 닿지 않으므로 자동으로 더미로 동작합니다. 의도를 분명히 하려면 `dummy` 를 명시하세요.
- 사용자 페이지는 `?table=12` 로 테이블을 지정합니다. 테이블별 QR 은 배포된 사용자 앱 주소 뒤에 이 값을 붙여 만드세요.

## 데이터 소스 전환 (더미 ↔ API)

화면(user·admin)의 데이터는 모두 **저장소 한 곳**을 거칩니다. 환경 변수 `DATA_SOURCE` 로 바꿉니다.

| 값 | 동작 |
|---|---|
| `auto` (기본) | 서버가 닿으면 API, 안 닿으면 더미 |
| `api` | 서버(`API_URL`, 기본 `http://127.0.0.1:8000`)에서만. 안 닿으면 오류 안내 |
| `dummy` | 코드 안의 더미만 (서버 불필요) |

```bash
DATA_SOURCE=api API_URL=http://127.0.0.1:8000 streamlit run user/app.py
DATA_SOURCE=dummy streamlit run admin/app.py     # 로그인 토큰은 ADMIN_TOKEN(기본 change-me)
```

| 구분 | 저장소 (여기만 보면 됨) | 더미 데이터 (= API 응답 명세) |
|---|---|---|
| user | `user/user_repository.py` | `user/menu_data.py`, `ai_quiz_data.py`, `recommendation_data.py` |
| admin | `admin/admin_repository.py` | `admin/admin_dummy_data.py` (서버와 같은 JSON 을 돌려주는 가짜 서버) |

- 더미 파일은 서버 응답과 **같은 JSON 모양**이라 변환 코드가 필요 없습니다. 서버 초기 데이터는 `python tools/export_dummy_seed.py` 로 더미에서 만듭니다.
- 새 데이터를 API로 바꾸려면: 저장소의 `ENDPOINTS` 에 경로 추가 → 가져오는 줄 추가 → 서버 응답을 더미와 같은 모양으로 맞추기. 맞는지는 `tests/test_admin_data_source.py`, `backend/tests/test_shop_admin.py` 의 계약 테스트가 확인합니다.
- 콘텐츠(카테고리·룰렛·직원호출 항목·AI 질문·추천 규칙)는 `GET /api/content`, 관리자는 `PUT /admin/api/content/{이름}` 으로 고치도록 되어 있으나, 지금은 둘 다 더미(`seed/content.json` 을 읽고, 저장은 하지 않음)입니다. 새 스키마에서는 `content` 테이블 없이 카테고리·룰렛 칸 등을 각각의 테이블로 나눕니다(`docs/DB_설계.md`).
- 서버 데이터는 10초 캐시되어 관리자가 바꾼 가격·품절이 곧 반영됩니다.

## 테스트

```bash
(cd backend && uv run pytest -q)          # 백엔드
python -m pytest tests -q                 # 화면+통합 (streamlit·pytest·backend 의존성이 모두 설치된 환경)
(cd user && python -m unittest test_ai_quiz test_cart test_recommendations)
```

- 완료 기준은 위 두 pytest 가 실패 없이 통과하는 것입니다(더미 상태인 기능의 테스트는 skip). 린터·포매터·빌드 설정은 없습니다.

## 규칙

- API 경로: 사용자용 `/api/...`, 관리자용 `/admin/api/...`
- CORS 허용 주소는 `backend/.env`의 `CORS_ORIGINS`에서 관리
