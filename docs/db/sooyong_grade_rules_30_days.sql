-- 수용 5: 기존 DB의 휴면 기본값을 30일로 통일한다. 테이블·회원·주문은 변경하지 않는다.
-- 관리자가 이미 다른 기준을 저장했다면 그 값은 유지한다. 반복 실행해도 안전하다.
begin;

create or replace function member_grade(visit_count integer, last_visit_at timestamptz,
                                        repeat_min integer default 2, regular_min integer default 5,
                                        dormant_days integer default 30)
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
                    coalesce((s.value->>'dormant')::int, 30)) as grade,
       (m.marketing_consent and not m.opted_out and m.phone is not null) as sms_sendable
from members m
left join app_settings s on s.key = 'grade_rule';

-- 과거 시드와 정확히 같은 기본값만 바꾸고, 별도로 저장된 기준은 덮어쓰지 않는다.
update app_settings
set value = '{"repeat":2,"regular":5,"dormant":30}'::jsonb, updated_at = now()
where key = 'grade_rule' and value = '{"repeat":2,"regular":5,"dormant":60}'::jsonb;

commit;
