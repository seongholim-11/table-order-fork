-- 메뉴 관리의 '이벤트' 체크 컬럼 추가 (Supabase SQL Editor 에서 한 번 실행).
-- 체크된 메뉴만 관리자 이벤트 페이지의 '서비스 메뉴' 선택 목록에 나온다.
-- 여러 번 실행해도 안전하다. 실행 전에도 앱은 동작한다(기본 이벤트 메뉴 8개만 목록에 나오고, 체크 저장은 무시됨).
alter table menus add column if not exists is_event boolean not null default false;

-- 지금 이벤트(룰렛)에서 쓰던 기본 메뉴 8개는 체크해 둔다. 기존 룰렛 설정이 그대로 유지된다.
update menus set is_event = true where id in ('a1','a4','a11','d7','d8','d1','j1','b1');
-- 이미 룰렛 칸에 저장된 서비스 메뉴도 체크해 둔다.
update menus set is_event = true where id in (select menu_id from roulette_prizes where menu_id is not null);
