-- 손님 응대 제안 카드의 '확인' 기록 테이블 (Supabase SQL Editor 에서 한 번 실행).
-- (손님, 주문) 한 쌍이 카드 하나이며, 행이 있으면 '확인', 없으면 '미확인'이다.
-- 여러 번 실행해도 안전하다. 서버가 처음 쓸 때 같은 표를 스스로 만들기도 한다.
create table if not exists service_tip_checks (
  member_id   bigint not null references members(id) on delete cascade,
  order_id    bigint not null references orders(id) on delete cascade,
  checked_at  timestamptz not null default now(),
  primary key (member_id, order_id)
);
alter table service_tip_checks enable row level security;
