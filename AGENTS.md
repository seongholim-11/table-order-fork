# AGENTS.md

## 프로젝트 개요
- 테이블 오더 모노레포(역전할머니맥주 홍대점 시연용). FastAPI 서버(`backend/`) + 손님 Streamlit(`user/`) + 관리자 Streamlit(`admin/`) + 공통 API 호출(`shared/`).
- 손님은 테이블 QR로 카카오 로그인 → 룰렛·쿠폰·주문·AI 추천을 쓰고, 관리자는 메뉴·주문·통계·고객·문자 마케팅을 다룬다.
- 소통·주석·커밋 메시지는 한국어로 한다.

## 실행·테스트 (모두 이 리포에서 확인한 명령)
```bash
# 서버 (http://127.0.0.1:8000/docs)
cd backend
cp .env.example .env
uv sync
uv run fastapi dev main.py

# 페이지 (backend/.env 의 APP_ENV=dev 면 손님은 모의 회원으로 자동 로그인, 관리자는 토큰 생략. dev 가 아니면 우회 없음)
# 페이지 (저장소 루트에서, 서버가 켜져 있어야 QR 로그인·문자 발송이 동작)
uv venv .venv
source .venv/Scripts/activate   # macOS/Linux 는 source .venv/bin/activate
uv pip install -r requirements.txt
streamlit run user/app.py --server.port 8501    # 사용자 (?table=12 로 테이블 지정)
streamlit run admin/app.py --server.port 8502   # 관리자 (APP_ENV=dev 면 토큰 입력 생략. 끄려면 ADMIN_SKIP_TOKEN=0, 토큰은 ADMIN_TOKEN)
```
- 서버 테스트: `cd backend && uv run pytest -q`
- 화면+통합 테스트: 저장소 루트에서 `python -m pytest tests -q` (streamlit·pytest·backend 의존성이 모두 설치된 환경 필요)
- 린터·포매터·빌드 설정은 없다. 완료 기준은 위 두 테스트가 실패 없이 통과하는 것(skip은 허용).

## 구조
- `backend/app/`: `routers/`(손님 API는 기능별 파일: user.py(회원·로그인 기록), store/menus/orders/coupons/roulette/staff_calls/ai/content.py, auth.py, admin/) → `services/` → `stores/`(SQL은 여기만) , `dummy/`(더미 응답, 담당별 `*_data.py`), `seed/`.
- `user/`, `admin/`: `app.py`는 진입점만. 화면은 `views/`, 공용 UI는 `ui/`, 세션 상태·계산은 `state/`. 폴더명을 `pages`로 쓰지 않는다(Streamlit 자동 멀티페이지 때문).
- 화면 코드는 `api`를 직접 부르지 않고 `user/user_repository.py`, `admin/admin_repository.py`만 부른다.
- API 경로: 손님 `/api/...`, 관리자 `/admin/api/...`. 기준 문서는 `docs/api/FBGrowth_API_경로_통합_정리_최종_v7_목록표만.md`, 담당 분배는 `docs/api/FBGrowth_API_담당_분배_3-2-2-2-1.md`.
- 담당자별 TODO: `docs/todo/TODO_{성호,재현,수용,서준,석원}.md`
- 문서 목록: `docs/팀_공지.md`(팀원 공지, 어떤 문서를 언제 보는지), `docs/todo/`(담당자별 TODO), `docs/api/`(API 경로·담당 분배), `docs/TODO_충돌_오류.md`(충돌·오류), `docs/개발_가이드.md`·`docs/DB_설계.md`·`docs/기능흐름_*.md`·`docs/코드_둘러보기.md`.
- TODO 진행 중 충돌·오류와 해결: `docs/TODO_충돌_오류.md`
- 상세: `docs/개발_가이드.md`(API 추가 순서), `docs/DB_설계.md`(DB 설계), `docs/기능흐름_*.md`(기능 흐름), `docs/코드_둘러보기.md`.

## 더미 상태 (팀원이 구현할 뼈대)
- 실제 구현은 **QR 로그인**(`/api/auth/*`, `/api/members/me`, `/api/tables/{n}/logins`), **문자 발송**(`/admin/api/marketing/sms/*`), 고객 목록(`GET /admin/api/members`), 손님 메뉴 목록(`GET /api/menus`), 관리자 메뉴 목록(`GET /admin/api/menus`)이다. 나머지 기능은 더미 응답을 돌려주거나 아직 구현되지 않았다.
- 아직 더미인 엔드포인트 찾기: `grep -rn "dummy\." backend/app/routers`, 목록은 `dummy.DUMMY_ENDPOINTS`.
- 실제 DB로 교체하는 방법: ① 라우터의 `dummy.xxx()` 호출을 store/service 호출로 바꾸고(라우터·stores의 TODO 주석, `NotImplementedError` 뼈대에 구현할 내용이 적혀 있음) ② `dummy/`의 해당 `*_data.py`에서 함수와 `ENDPOINTS` 줄을 지우고(`dummy/__init__.py`는 고치지 않는다) ③ 해당 테스트의 `skip`을 제거한다. 이전 구현 참고: 커밋 `a8b3d14`.
- 교체가 끝나 더미가 없어지면 이 섹션을 삭제한다.

## 정해진 제품 규칙 (어기지 말 것)
- 주문 상태 기능·UI는 없다(접수/조리중 같은 상태를 만들지 않는다).
- 방문 횟수는 로그인할 때마다 +1.
- 룰렛: 회원당 하루 1회(KST). 같은 날 다른 테이블에서도 불가, 다른 날은 가능. 당첨은 즉시 적용하지 않고 `coupons`(쿠폰함)에 넣고, 주문 화면 쿠폰함에서 사용/취소하며 주문 시 `used_at` 기록. 유효기간은 미정.
- 테이블 누적 주문(`GET /v1/tables/{id}/orders`)은 `table_logins`의 로그인 시각 이후 주문만 합산한다. `table_sessions` 같은 별도 테이블을 만들지 않는다.
- AI 챗봇은 제미나이 무료 API를 쓰고 RAG 없이 DB 데이터를 근거로 답한다.
- 문자 발송은 솔라피. `SMS_DRY_RUN=true`(기본)이면 실제 전송 없이 기록만 한다.
- 관리자 인증(Supabase Auth `owners`)은 모든 개발이 끝난 뒤 마지막에 한다. 지금은 `ADMIN_TOKEN` 방식을 쓰고, 챗봇 `owner_id` 문제도 그때까지 보류.
- DB 설계는 `docs/DB_설계.md`와 `docs/db/fbgrowth_schema.sql`이 기준이며 Supabase `table-order` 프로젝트에 적용되어 있다. 서버 `stores/`는 아직 SQLite 호환 구조이므로 Supabase 스키마로 옮기는 작업이 남아 있다.

## 작업 원칙
- 수정하는 파일 수를 최대한 줄인다. 요청과 무관한 파일은 건드리지 않는다.
- 기존 코드를 최대한 유지한다. 꼭 필요한 부분만 고치고, 관련 없는 정리·이름 변경·재배치는 하지 않는다.
- 새로 추가한 코드와 로직에는 초급 개발자도 이해할 수 있게 한국어 주석을 단다(무엇을, 왜 하는지).
- **TODO 체크**: 작업을 끝낸 항목은 본인 `docs/todo/TODO_*.md`에서 `- [ ]`를 `- [x]`로 바꾸고, 맨 위 "진행 순서" 표의 상태도 맞춘 뒤 같은 PR에 포함한다. 테스트까지 통과한 항목만 체크한다.

## 금지 구역
- `.env`, 비밀 키(`SOLAPI_*`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, `ADMIN_TOKEN`)를 커밋하거나 화면·로그에 노출하지 않는다.
- 스키마(`stores/*.py`의 `SCHEMA`, `docs/db/*.sql`)를 바꾸면 `docs/DB_설계.md`도 함께 고치고 팀에 알린다. 기존 `backend/app.db`에는 반영되지 않으므로 지우고 서버를 다시 켠다.
- 라우터에서 SQL을 쓰지 않는다(`stores/` 메서드만).
- 테스트를 skip·삭제해서 통과시키지 않는다(더미 교체 시 skip 제거만 허용).

## Git 규칙
- 조직 소유 본 리포를 팀원이 각자 **포크**해서 개발하고, **PR은 본 리포의 `dev` 브랜치로만** 보낸다. `main`으로 직접 PR·push 하지 않는다.
- 본 리포의 `main`에는 SEONGHO가 `dev`의 코드를 확인한 뒤 머지한다.
- 팀원은 포크한 본인 리포의 **`main`에서 계속 개발**한다(작업용 브랜치를 따로 만들지 않는다). 본 리포에는 팀원 포크의 `main`에서 `dev`로 PR을 보낸다. 본 리포 `main`에는 직접 PR·push 하지 않는다.
- 작업을 시작하기 전에 본 리포 `dev`를 내 포크 `main`에 맞춘다(충돌을 줄이기 위해 작업 시작 전과 PR 직전에 한다):
  ```bash
  git remote add upstream https://github.com/aio-03-p1-team1/table-order.git   # 최초 1회
  git fetch upstream && git pull --rebase upstream dev                        # 내 main에 최신 dev 반영
  ```
- PR을 보내기 전에 위 테스트를 돌려 통과를 확인한다. 문제가 있으면 PR을 보내지 말고 먼저 고치거나 보고한다.
- **한 PR에는 TODO 항목 하나만** 담는다. 포크 `main`에서 바로 보내므로 여러 작업이 섞이면 일부만 되돌리기 어렵다. 한 항목을 끝내면 PR을 보내고, 머지된 뒤에 다음 항목을 시작한다.

### 커밋 메시지
- 첫 줄: `종류: 한글 요약` (종류는 `feat`·`fix`·`docs`·`refactor`·`chore`·`test`). 50자 안팎, 마침표 없이 "~추가", "~수정"처럼 끝낸다.
- 빈 줄 다음 본문에 **무엇을·왜** 바꿨는지 적는다. TODO 항목이 있으면 번호를 쓴다(예: `TODO_수용 2-3`).
- 좋은 예
  ```
  feat: 룰렛 하루 1회 제한 추가

  같은 회원이 같은 날(KST) 다시 돌리면 409를 돌려준다. 다른 테이블에서도 막는다.
  TODO_수용 3-2
  ```
  ```
  fix: 쿠폰 사용 취소 시 used_at 초기화
  ```
- 나쁜 예: `수정`, `작업중`, `ㅇㅇ`, `fix: 이것저것 고침` (무엇을 왜 바꿨는지 알 수 없다).

### PR 메시지
- 제목: `종류: 한글 요약 (TODO_담당 항목번호)` 예) `feat: 룰렛 하루 1회 제한 (TODO_수용 3-2)`
- 본문에는 **변경 내용, 테스트 방법, 테스트 결과, 미해결 문제**를 반드시 적는다(없으면 "없음").
  ```
  ## 변경 내용
  - 룰렛 스핀 전에 오늘(KST) 기록이 있는지 확인하고, 있으면 409 반환
  ## 테스트 방법
  - cd backend && uv run pytest -q / 루트에서 python -m pytest tests -q
  ## 테스트 결과
  - 서버 123 passed, 화면 45 passed
  ## 미해결 문제
  - 없음
  ```
- 빌드 명령·폴더 구조·규칙이 바뀌는 변경에는 이 파일도 함께 갱신한다.
