-- F&BGrowth Supabase(Postgres) 스키마 — API v6 목록표 기준 (2026-10-15)
-- 실행 순서: 이 파일 전체를 SQL Editor 또는 마이그레이션으로 한 번에 실행. 여러 번 실행해도 되도록 IF NOT EXISTS 사용.
-- 서버(FastAPI)는 DATABASE_URL(서비스 롤)로 접속하므로 RLS를 우회한다. RLS는 브라우저·anon 키 접근을 막는 안전장치.
-- 시각은 모두 timestamptz(UTC 저장), 화면 표시는 KST로 변환.

-- =====================================================================
-- 0. 공통 함수
-- =====================================================================
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- =====================================================================
-- 1. 매장·메뉴 (손님/관리자 공용 콘텐츠)
-- =====================================================================
-- GET /api/v1/store
create table if not exists store_info (
  id          smallint primary key default 1 check (id = 1),   -- 매장 1개 (한 줄만 허용)
  name        text not null,
  branch      text not null,
  slogan      text not null default '',
  tables      integer not null default 30 check (tables >= 1)  -- 전체 테이블 수 (?table= 번호 검증)
);

-- GET /api/v1/categories, POST·PATCH·DELETE /api/v1/owner/categories
create table if not exists categories (
  id          text primary key,
  name        text not null unique,
  icon        text not null default '🍽️',
  color_from  text not null default '#a29bfe',                  -- 메뉴 카드 그라데이션 시작색
  color_to    text not null default '#4b3f9e',
  is_virtual  boolean not null default false,                   -- 'ai'(AI 추천 조합)·'best'(인기메뉴): 메뉴를 직접 넣지 않음
  sort_order  integer not null default 0
);

-- GET /api/v1/menus, /api/v1/owner/menus 및 POST·PATCH·DELETE, PATCH weights
create table if not exists menus (
  id           text primary key,
  category_id  text not null references categories(id) on update cascade on delete restrict,  -- 메뉴가 있으면 카테고리 삭제 불가
  name         text not null,
  description  text not null default '',
  price        integer not null check (price >= 0),
  emoji        text not null default '🍽️',
  tags         text[] not null default '{}',                    -- 예: {BEST,매운맛}
  is_soldout   boolean not null default false,
  spicy        smallint not null default 0 check (spicy between 0 and 3),   -- 0 안 매움 … 3 아주 매움
  weight       smallint not null default 50 check (weight between 0 and 100), -- 추천 가중치
  set_ok       boolean not null default false,                  -- AI 추천 세트에 넣을 수 있는지
  image_url    text not null default '',
  sort_order   integer not null default 0,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists menus_category_idx on menus (category_id, sort_order);

create or replace function menus_reject_virtual_category() returns trigger language plpgsql as $$
begin
  if exists (select 1 from categories where id = new.category_id and is_virtual) then
    raise exception '가상 카테고리(%)에는 메뉴를 넣을 수 없습니다.', new.category_id;
  end if;
  return new;
end $$;
drop trigger if exists menus_virtual_check on menus;
create trigger menus_virtual_check before insert or update of category_id on menus
  for each row execute function menus_reject_virtual_category();
drop trigger if exists menus_updated_at on menus;
create trigger menus_updated_at before update on menus for each row execute function set_updated_at();

-- =====================================================================
-- 2. 회원·로그인·룰렛
-- =====================================================================
-- GET /api/v1/members/me, 카카오 로그인(auth/kakao/*), 고객 목록(GET /api/admin/customers)
create table if not exists members (
  id                    bigint generated always as identity primary key,
  kakao_id              text not null unique,
  auth_user_id          uuid unique references auth.users(id) on delete set null,  -- Supabase Auth 로그인 연결(선택)
  nickname              text not null,
  phone                 text,
  gender                text check (gender in ('male', 'female')),
  birthday              text,                                   -- 카카오가 주는 MMDD 등 원문
  birth_year            smallint,
  marketing_consent     boolean not null default false,         -- 광고성 문자 수신 동의 (kakao/continue 에서 기록)
  marketing_consent_at  timestamptz,
  opted_out             boolean not null default false,         -- 수신거부 (동의보다 우선)
  opted_out_at          timestamptz,
  visit_count           integer not null default 0,             -- 로그인할 때마다 +1 (주문 횟수가 아님)
  last_visit_at         timestamptz,
  created_at            timestamptz not null default now()
);
create index if not exists members_last_visit_idx on members (last_visit_at);

-- POST /api/v1/auth/qr, GET /api/v1/auth/qr/{secret}, kakao/start·continue·callback
-- 서버 메모리에 있던 QR 로그인 세션을 DB로 옮겨 서버가 여러 개여도 동작하게 한다. 로그인 토큰(JWT)은 저장하지 않는다.
create table if not exists login_sessions (
  id                  uuid primary key default gen_random_uuid(),
  token               text not null unique,                     -- QR에 들어가는 값(휴대폰용)
  secret              text not null unique,                     -- 태블릿만 아는 값(폴링·WebSocket 인증)
  table_no            integer not null check (table_no >= 1),
  status              text not null default 'waiting'
                      check (status in ('waiting', 'scanned', 'logged_in', 'rejected', 'expired')),
  member_id           bigint references members(id) on delete set null,
  blocked_member_ids  bigint[] not null default '{}',           -- 이 태블릿에서 이미 로그인한 회원(중복 로그인 차단)
  marketing_consent   boolean not null default false,
  pkce_verifier       text,
  claimed             boolean not null default false,           -- 태블릿이 결과를 이미 받아갔는지(한 번만 전달)
  created_at          timestamptz not null default now(),
  expires_at          timestamptz not null
);
create index if not exists login_sessions_expires_idx on login_sessions (expires_at);

-- GET /api/v1/roulette/prizes, PUT /api/v1/owner/roulette/prizes (칸 2~8개, 가중치 합 0 초과는 서버에서 검증)
create table if not exists roulette_prizes (
  id          bigint generated always as identity primary key,
  label       text not null,                                    -- 칸에 보이는 문구
  short_text  text not null,                                    -- 당첨 안내문
  emoji       text not null default '🎁',
  color       text not null check (color ~* '^#[0-9a-f]{6}$'),
  kind        text not null check (kind in ('discount', 'free')),
  percent     smallint check (percent between 1 and 100),       -- 할인 칸
  menu_id     text references menus(id) on update cascade on delete restrict,  -- 서비스 칸의 무료 메뉴
  weight      numeric not null default 1 check (weight >= 0),   -- 당첨 확률 가중치
  sort_order  integer not null default 0,
  check ((kind = 'discount' and percent is not null and menu_id is null)
      or (kind = 'free' and menu_id is not null and percent is null))
);

-- GET /api/v1/roulette/status, POST /api/v1/roulette/plays
-- 한 테이블(태블릿)에서 하루 동안 로그인한 회원과 룰렛 사용 결과. 회원당 하루 1회.
create table if not exists table_logins (
  id               bigint generated always as identity primary key,
  table_no         integer not null check (table_no >= 1),
  member_id        bigint not null references members(id) on delete cascade,
  login_day        date not null default ((now() at time zone 'Asia/Seoul')::date),
  logged_in_at     timestamptz not null default now(),
  roulette_eligible boolean not null default true,              -- 처음 로그인한 회원만 룰렛 기회
  prize_id         bigint references roulette_prizes(id) on delete set null,
  prize_text       text,                                        -- 당첨 안내문 사본(칸이 바뀌어도 기록 유지)
  played_at        timestamptz,
  unique (table_no, member_id, login_day)
);
-- 룰렛은 회원당 하루 1회: 같은 날 다른 테이블에서도 돌릴 수 없고, 다음 날은 가능 (login_day 는 KST 기준 날짜)
create unique index if not exists table_logins_one_play_per_day on table_logins (member_id, login_day)
  where played_at is not null;

-- =====================================================================
-- 3. 주문·직원 호출
-- =====================================================================
-- 3-1. AI 추천 노출 기록 (POST /api/v1/ai/recommendations 가 저장, 관리자 AI 적중률의 분모)
create table if not exists recommendation_events (
  id            bigint generated always as identity primary key,
  table_no      integer not null check (table_no >= 1),
  member_id     bigint references members(id) on delete set null,
  answers       jsonb not null default '{}',                    -- people·budget·spicy·hunger·stress·kind·intent·gender
  hour          smallint check (hour between 0 and 23),
  weather_code  text,
  combo_ids     text[] not null default '{}',
  created_at    timestamptz not null default now()
);
create index if not exists recommendation_events_created_idx on recommendation_events (created_at);

-- 3-2. 주문 (POST /api/v1/orders, GET /api/v1/tables/{tableId}/orders, GET /api/v1/owner/orders)
create table if not exists orders (
  id                        bigint generated always as identity primary key,
  table_no                  integer not null check (table_no >= 1),
  member_id                 bigint references members(id) on delete set null,   -- 비회원 주문은 null
  total                     integer not null check (total >= 0),                -- 할인 반영 후 결제 금액
  roulette_discount_percent smallint not null default 0 check (roulette_discount_percent between 0 and 100),
  ai_combo                  boolean not null default false,                     -- AI 추천 조합이 포함된 주문
  recommendation_event_id   bigint references recommendation_events(id) on delete set null,
  created_at                timestamptz not null default now()
);
create index if not exists orders_created_idx on orders (created_at desc);
create index if not exists orders_table_idx on orders (table_no, created_at desc);
create index if not exists orders_member_idx on orders (member_id, created_at desc);

create table if not exists order_items (
  id                   bigint generated always as identity primary key,
  order_id             bigint not null references orders(id) on delete cascade,
  menu_id              text references menus(id) on update cascade on delete set null,  -- 조합 줄은 null
  kind                 text not null default 'menu' check (kind in ('menu', 'combo', 'roulette_service')),
  name                 text not null,                           -- 주문 시점 이름 사본(메뉴가 바뀌거나 지워져도 기록 유지)
  option_label         text not null default '',
  unit_price           integer not null check (unit_price >= 0),
  original_unit_price  integer check (original_unit_price >= 0),   -- 조합 할인 전 단가
  qty                  smallint not null check (qty between 1 and 99)
);
create index if not exists order_items_order_idx on order_items (order_id);

-- AI 조합 줄의 구성 메뉴 (인기 메뉴 집계는 조합을 구성 메뉴 단위로 센다)
create table if not exists order_item_components (
  id             bigint generated always as identity primary key,
  order_item_id  bigint not null references order_items(id) on delete cascade,
  menu_id        text references menus(id) on update cascade on delete set null,
  name           text not null,
  option_label   text not null default '',
  qty            smallint not null check (qty >= 1)
);
create index if not exists order_item_components_item_idx on order_item_components (order_item_id);

-- 쿠폰함: GET /api/v1/coupons, GET /api/tables/{n}/coupons, POST /api/orders(coupon_ids)
-- 룰렛에 당첨되면 쿠폰이 한 장 생기고(table_login_id 로 어느 룰렛 기록인지 연결), 주문에 쓰면 used_at 이 채워진다.
create table if not exists coupons (
  id             bigint generated always as identity primary key,
  member_id      bigint not null references members(id) on delete cascade,
  table_login_id bigint unique references table_logins(id) on delete set null,  -- 룰렛 한 번에 쿠폰 한 장
  table_no       integer not null check (table_no >= 1),                       -- 받은 테이블
  prize_id       bigint references roulette_prizes(id) on delete set null,
  kind           text not null check (kind in ('discount', 'free')),
  label          text not null,                                                -- 당첨 안내문 사본(칸이 바뀌어도 유지)
  emoji          text not null default '🎁',
  percent        smallint check (percent between 1 and 100),                   -- 할인 쿠폰
  menu_id        text references menus(id) on update cascade on delete set null,  -- 서비스 쿠폰의 무료 메뉴
  issued_at      timestamptz not null default now(),
  expires_at     timestamptz,                                                  -- 유효기간 정책 미정: null = 없음
  used_at        timestamptz,                                                  -- null 이면 사용 가능
  used_order_id  bigint references orders(id) on delete set null,
  check ((kind = 'discount' and percent is not null) or (kind = 'free' and percent is null))
);
create index if not exists coupons_member_idx on coupons (member_id, used_at);
create index if not exists coupons_order_idx on coupons (used_order_id);
create index if not exists coupons_menu_idx on coupons (menu_id);
create index if not exists coupons_prize_idx on coupons (prize_id);

-- 3-3. 직원 호출 (POST /api/v1/staff-calls, GET /api/v1/staff-call-items)
create table if not exists staff_call_items (
  id          bigint generated always as identity primary key,
  label       text not null unique check (char_length(label) between 1 and 20),
  sort_order  integer not null default 0
);

create table if not exists staff_calls (
  id          bigint generated always as identity primary key,
  table_no    integer not null check (table_no >= 1),
  items       text[] not null check (cardinality(items) >= 1),
  created_at  timestamptz not null default now(),
  done_at     timestamptz                                       -- 관리자 처리 화면은 제거됨. 처리 기능을 되살릴 때 사용
);
create index if not exists staff_calls_created_idx on staff_calls (created_at desc);

-- =====================================================================
-- 4. AI 추천 콘텐츠 (GET /api/v1/ai/questions, /weather/current, /ai/recommendation-rules)
-- =====================================================================
create table if not exists quiz_questions (
  id          text primary key,                                 -- hunger, stress, people, gender, kind, spicy, intent, budget
  group_name  text not null,
  title       text not null,
  sort_order  integer not null default 0
);

create table if not exists quiz_options (
  id           bigint generated always as identity primary key,
  question_id  text not null references quiz_questions(id) on update cascade on delete cascade,
  value        text not null,
  label        text not null,
  emoji        text not null default '',
  sort_order   integer not null default 0,
  unique (question_id, value)
);

create table if not exists weather_types (
  code   text primary key,                                      -- sunny, cloudy, rain, snow, hot
  label  text not null,
  icon   text not null
);

create table if not exists weather_current (                    -- 현재 날씨 한 줄 (외부 날씨 API 연동 전에는 수동·더미)
  id          smallint primary key default 1 check (id = 1),
  code        text not null references weather_types(code),
  source      text not null default 'dummy',
  updated_at  timestamptz not null default now()
);

-- 추천 규칙: discount_percent, pairings, drinks, pair_meta 등 모양이 복잡해 키별 JSON으로 보관
create table if not exists recommendation_rules (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now()
);

-- =====================================================================
-- 5. 관리자: 계정·설정·알림·마케팅·챗봇
-- =====================================================================
-- GET /api/v1/owner/me — Supabase Auth 사용자 중 사장님 계정
create table if not exists owners (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  role        text not null default 'OWNER' check (role = 'OWNER'),
  created_at  timestamptz not null default now()
);

-- 설정 값: grade_rule(등급 기준 기본값), sms_limits(월 무료 한도) 등
create table if not exists app_settings (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now()
);

-- GET /api/admin/alerts, PATCH /api/admin/alerts/{alertId}
create table if not exists alerts (
  id               bigint generated always as identity primary key,
  kind             text not null check (kind in ('dormant', 'soldout', 'other')),
  title            text not null,
  detail           text not null default '',
  member_id        bigint references members(id) on delete cascade,
  menu_id          text references menus(id) on update cascade on delete cascade,
  created_at       timestamptz not null default now(),
  acknowledged_at  timestamptz
);
create index if not exists alerts_open_idx on alerts (created_at desc) where acknowledged_at is null;

-- 문자 마케팅: sms/usage·preview·candidates·send·logs·cancel, customers/{id}/opt-out
create table if not exists sms_logs (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),
  month         char(7) not null,                               -- 'YYYY-MM' (월 한도 집계 기준)
  request_id    text,                                           -- 문자 발송 업체 요청 ID
  type          text not null check (type in ('SMS', 'LMS')),
  content       text not null,
  target_count  integer not null check (target_count >= 0),
  status        text not null check (status in ('sent', 'dry_run', 'failed', 'scheduled', 'canceled')),
  error         text,
  scheduled_at  timestamptz
);
create index if not exists sms_logs_month_idx on sms_logs (month);

create table if not exists sms_log_recipients (                 -- 누구에게 보냈는지(체크 해제로 제외된 회원은 없음)
  log_id     bigint not null references sms_logs(id) on delete cascade,
  member_id  bigint not null references members(id) on delete cascade,
  primary key (log_id, member_id)
);

-- GET /api/admin/marketing/external-context — 오늘 날씨·지역 행사 문구(AI 문자 후보용)
create table if not exists external_context (
  day           date primary key,
  weather_text  text not null default '',
  event_text    text not null default '',
  updated_at    timestamptz not null default now()
);

-- AI 챗봇: POST·GET·DELETE /api/admin/marketing/chat/sessions…, POST …/messages
create table if not exists chat_sessions (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references auth.users(id) on delete cascade,
  title       text not null default '새 대화',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists chat_sessions_owner_idx on chat_sessions (owner_id, updated_at desc);
drop trigger if exists chat_sessions_updated_at on chat_sessions;
create trigger chat_sessions_updated_at before update on chat_sessions for each row execute function set_updated_at();

create table if not exists chat_messages (
  id          bigint generated always as identity primary key,
  session_id  uuid not null references chat_sessions(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  created_at  timestamptz not null default now()
);
create index if not exists chat_messages_session_idx on chat_messages (session_id, id);

-- =====================================================================
-- 6. 계산값: 고객 등급, 문자 월 사용량
-- =====================================================================
-- 고객 등급 (GET /api/admin/customers, customers/grades). 휴면 → 단골 → 재방문 → 신규 순으로 판정.
create or replace function member_grade(visit_count integer, last_visit_at timestamptz,
                                        repeat_min integer default 2, regular_min integer default 5,
                                        dormant_days integer default 60)
returns text language sql stable as $$
  select case
    when last_visit_at is not null
         and ((now() at time zone 'Asia/Seoul')::date - (last_visit_at at time zone 'Asia/Seoul')::date) >= dormant_days then '휴면'
    when visit_count >= regular_min then '단골'
    when visit_count >= repeat_min then '재방문'
    else '신규'
  end
$$;

create or replace view v_members_graded with (security_invoker = true) as
select m.*,
       member_grade(m.visit_count, m.last_visit_at,
                    coalesce((s.value->>'repeat')::int, 2),
                    coalesce((s.value->>'regular')::int, 5),
                    coalesce((s.value->>'dormant')::int, 60)) as grade,
       (m.marketing_consent and not m.opted_out and m.phone is not null) as sms_sendable
from members m
left join app_settings s on s.key = 'grade_rule';

-- 이번 달 문자 사용량 (GET /api/admin/marketing/sms/usage). 취소·실패는 제외.
create or replace view v_sms_usage with (security_invoker = true) as
select month, type, sum(target_count)::int as used
from sms_logs
where status in ('sent', 'dry_run', 'scheduled')
group by month, type;

-- =====================================================================
-- 7. 보안(RLS): 모두 켜고, 손님 화면이 읽는 공개 콘텐츠만 읽기 허용
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array[
    'store_info','categories','menus','members','login_sessions','roulette_prizes','table_logins',
    'recommendation_events','orders','order_items','order_item_components','coupons','staff_call_items','staff_calls',
    'quiz_questions','quiz_options','weather_types','weather_current','recommendation_rules',
    'owners','app_settings','alerts','sms_logs','sms_log_recipients','external_context','chat_sessions','chat_messages']
  loop
    execute format('alter table %I enable row level security', t);
  end loop;

  foreach t in array array[
    'store_info','categories','menus','roulette_prizes','staff_call_items',
    'quiz_questions','quiz_options','weather_types','weather_current','recommendation_rules']
  loop
    execute format('drop policy if exists "public read" on %I', t);
    execute format('create policy "public read" on %I for select to anon, authenticated using (true)', t);
  end loop;
end $$;

-- 사장님은 자기 대화만 본다 (서버를 거치지 않고 Supabase 클라이언트로 읽을 때를 대비)
drop policy if exists "owner own sessions" on chat_sessions;
create policy "owner own sessions" on chat_sessions for all to authenticated
  using (owner_id = auth.uid()) with check (owner_id = auth.uid());
drop policy if exists "owner own messages" on chat_messages;
create policy "owner own messages" on chat_messages for all to authenticated
  using (exists (select 1 from chat_sessions s where s.id = session_id and s.owner_id = auth.uid()))
  with check (exists (select 1 from chat_sessions s where s.id = session_id and s.owner_id = auth.uid()));

-- =====================================================================
-- 8. 기본값(시드): 설정·날씨 종류. 메뉴·카테고리·룰렛·질문·규칙은 backend/app/seed/*.json 에서 불러온다.
-- =====================================================================
insert into app_settings (key, value) values
  ('grade_rule', '{"repeat": 2, "regular": 5, "dormant": 60}'),
  ('sms_limits', '{"SMS": 50, "LMS": 10}')
on conflict (key) do nothing;

insert into weather_types (code, label, icon) values
  ('sunny', '맑음', '☀️'), ('cloudy', '흐림', '☁️'), ('rain', '비', '🌧️'), ('snow', '눈', '❄️'), ('hot', '무더위', '🥵')
on conflict (code) do nothing;
insert into weather_current (id, code) values (1, 'sunny') on conflict (id) do nothing;
