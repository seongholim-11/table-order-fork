# Table Order

FastAPI 서버 + 사용자 페이지 + 관리자 페이지를 한 저장소에서 관리하는 모노레포입니다. (역전할머니맥주 홍대점 시연용)

> **현재 상태**: 서버에 실제로 구현된 기능은 **QR 로그인**, **문자 발송(솔라피)**, **고객 목록·수신거부**입니다. 나머지 엔드포인트는 `backend/app/dummy/` 의 더미 응답을 돌려주고 저장하지 않습니다(팀원이 하나씩 DB로 구현 중). 자세한 내용은 `AGENTS.md` 의 "더미 상태"를 보세요.

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
