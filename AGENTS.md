# AGENTS.md

## 프로젝트 개요
- 테이블 오더 모노레포(역전할머니맥주 홍대점 시연용). FastAPI 서버(`backend/`) + 손님 Streamlit(`user/`) + 관리자 Streamlit(`admin/`) + 공통 API 호출(`shared/`).
- 손님은 테이블 QR로 카카오 로그인 → 룰렛·쿠폰·주문·AI 추천을 쓰고, 관리자는 메뉴·주문·통계·고객·문자 마케팅을 다룬다.
- 소통·주석·커밋 메시지는 한국어로 한다.

## 실행·테스트 (모두 이 리포에서 확인한 명령)
- 서버 설치·실행: `cd backend && cp .env.example .env && uv sync && uv run fastapi dev main.py` (http://127.0.0.1:8000/docs)
- 화면 설치: `uv venv .venv && uv pip install -r requirements.txt`
- 화면 실행(서버 없이 더미): `DATA_SOURCE=dummy streamlit run user/app.py` / `streamlit run admin/app.py --server.port 8502`
- 서버 테스트: `cd backend && uv run pytest -q`
- 화면+통합 테스트: 저장소 루트에서 `python -m pytest tests -q` (streamlit·pytest·backend 의존성이 모두 설치된 환경 필요)
- 린터·포매터·빌드 설정은 없다. 완료 기준은 위 두 테스트가 실패 없이 통과하는 것(skip은 허용).

## 구조
- `backend/app/`: `routers/`(user.py, auth.py, admin/) → `services/` → `stores/`(SQL은 여기만) , `dummy.py`(더미 응답), `seed/`.
- `user/`, `admin/`: `app.py`는 진입점만. 화면은 `views/`, 공용 UI는 `ui/`, 세션 상태·계산은 `state/`. 폴더명을 `pages`로 쓰지 않는다(Streamlit 자동 멀티페이지 때문).
- 화면 코드는 `api`를 직접 부르지 않고 `user/user_repository.py`, `admin/admin_repository.py`만 부른다.
- API 경로: 손님 `/api/...`, 관리자 `/admin/api/...`. 기준 문서는 `/mnt/project-files/api/FBGrowth_API_경로_통합_정리_최종_v7_목록표만.md`(프로젝트 파일).
- 상세: `docs/DEVELOPMENT_GUIDE.md`(API 추가 순서), `docs/DB_SCHEMA.md`(DB 설계), `docs/FLOW_*.md`(기능 흐름), `docs/CODE_TOUR.md`.

## 더미 상태 (팀원이 구현할 뼈대)
- 실제 구현은 **QR 로그인**(`/api/auth/*`, `/api/members/me`, `/api/tables/{n}/logins`)과 **문자 발송**(`/admin/api/marketing/sms/*`), 고객 목록(`GET /admin/api/members`)뿐이다. 나머지 엔드포인트는 `backend/app/dummy.py`의 더미 응답을 돌려주고 저장하지 않는다.
- 아직 더미인 엔드포인트 찾기: `grep -rn "dummy\." backend/app/routers`, 목록은 `dummy.DUMMY_ENDPOINTS`.
- 실제 DB로 교체하는 방법: ① 라우터의 `dummy.xxx()` 호출을 store/service 호출로 바꾸고(라우터·stores의 TODO 주석, `NotImplementedError` 뼈대에 구현할 내용이 적혀 있음) ② `dummy.py`의 해당 함수와 `DUMMY_ENDPOINTS` 줄을 지우고 ③ 해당 테스트의 `skip`을 제거한다. 이전 구현 참고: 커밋 `a8b3d14`.
- 교체가 끝나 더미가 없어지면 이 섹션을 삭제한다.

## 정해진 제품 규칙 (어기지 말 것)
- 주문 상태 기능·UI는 없다(접수/조리중 같은 상태를 만들지 않는다).
- 방문 횟수는 로그인할 때마다 +1.
- 룰렛: 회원당 하루 1회(KST). 같은 날 다른 테이블에서도 불가, 다른 날은 가능. 당첨은 즉시 적용하지 않고 `coupons`(쿠폰함)에 넣고, 주문 화면 쿠폰함에서 사용/취소하며 주문 시 `used_at` 기록. 유효기간은 미정.
- 테이블 누적 주문(`GET /v1/tables/{id}/orders`)은 `table_logins`의 로그인 시각 이후 주문만 합산한다. `table_sessions` 같은 별도 테이블을 만들지 않는다.
- AI 챗봇은 제미나이 무료 API를 쓰고 RAG 없이 DB 데이터를 근거로 답한다.
- 문자 발송은 솔라피. `SMS_DRY_RUN=true`(기본)이면 실제 전송 없이 기록만 한다.
- 관리자 인증(Supabase Auth `owners`)은 모든 개발이 끝난 뒤 마지막에 한다. 지금은 `ADMIN_TOKEN` 방식을 쓰고, 챗봇 `owner_id` 문제도 그때까지 보류.
- DB 설계는 `docs/DB_SCHEMA.md`와 `docs/db/fbgrowth_schema.sql`이 기준이며 Supabase `table-order` 프로젝트에 적용되어 있다. 서버 `stores/`는 아직 SQLite 호환 구조이므로 Supabase 스키마로 옮기는 작업이 남아 있다.

## 작업 원칙
- 수정하는 파일 수를 최대한 줄인다. 요청과 무관한 파일은 건드리지 않는다.
- 기존 코드를 최대한 유지한다. 꼭 필요한 부분만 고치고, 관련 없는 정리·이름 변경·재배치는 하지 않는다.
- 새로 추가한 코드와 로직에는 초급 개발자도 이해할 수 있게 한국어 주석을 단다(무엇을, 왜 하는지).

## 금지 구역
- `.env`, 비밀 키(`SOLAPI_*`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, `ADMIN_TOKEN`)를 커밋하거나 화면·로그에 노출하지 않는다.
- 스키마(`stores/*.py`의 `SCHEMA`, `docs/db/*.sql`)를 바꾸면 `docs/DB_SCHEMA.md`도 함께 고치고 팀에 알린다. 기존 `backend/app.db`에는 반영되지 않으므로 지우고 서버를 다시 켠다.
- 라우터에서 SQL을 쓰지 않는다(`stores/` 메서드만).
- 테스트를 skip·삭제해서 통과시키지 않는다(더미 교체 시 skip 제거만 허용).

## Git 규칙
- 조직 소유 본 리포를 팀원이 각자 **포크**해서 개발하고, **PR은 본 리포의 `dev` 브랜치로만** 보낸다. `main`으로 직접 PR·push 하지 않는다.
- 본 리포의 `main`에는 SEONGHO가 `dev`의 코드를 확인한 뒤 머지한다.
- 포크한 본인 리포에서는 작업마다 새 브랜치를 만든다. 이름은 `feat/`·`fix/`·`docs/`·`refactor/`·`chore/`·`test/` + 한글 설명으로 짓는다(예: `feat/룰렛-하루-1회-제한`). `dev`·`main`에서 바로 작업하지 않는다.
- PR을 보내기 전에 위 테스트를 돌려 통과를 확인한다. 문제가 있으면 PR을 보내지 말고 먼저 고치거나 보고한다.
- PR 본문에는 **변경 내용, 테스트 방법, 테스트 결과, 미해결 문제**를 반드시 적는다(없으면 "없음").
- 빌드 명령·폴더 구조·규칙이 바뀌는 변경에는 이 파일도 함께 갱신한다.
