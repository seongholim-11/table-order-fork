-- 샘플 데이터: "실제 손님이 다녀간 것처럼" 보이는 시연용 데이터 (고객 40명, 최근 30일 로그인·룰렛·쿠폰·주문·직원 호출·문자 등)
-- 여러 번 실행해도 안전: 먼저 이전 샘플을 지우고 다시 넣는다. 날짜는 실행하는 날(KST) 기준으로 만든다.
-- 구분 표시: 회원 kakao_id 'sample-001'~, 닉네임 '[샘플] ...' / 알림·문자 내용 '[샘플]' / 직원 호출은 done_at 이 채워진 것.
-- 삭제: fbgrowth_sample_data_cleanup.sql. 메뉴·룰렛·퀴즈 시드(fbgrowth_seed.sql)가 먼저 들어가 있어야 한다.
do $$
declare
  v_today date := (now() at time zone 'Asia/Seoul')::date;   -- 오늘(KST)
  v_names text[] := array['김민준','이서연','박지후','최수아','정도윤','강하은','조시우','윤서진','장예준','임지아',
                          '한유진','오건우','서민서','신재원','권나연','황태민','안소율','송현우','류아린','홍지훈'];
  mids bigint[] := '{}';
  v_id bigint; v_tl bigint; v_cid bigint; v_oid bigint; v_iid bigint; v_evt bigint;
  v_prize roulette_prizes%rowtype;
  v_ans jsonb; v_w text; v_combo text[]; v_sum integer; v_sub bigint; v_pct integer;
  v_login timestamptz; v_tn integer; d date;
  i int; k int; target int; lastoff int; gap int; n int;
  v_ai boolean; v_used boolean;
  it record; r record; v_log bigint;
begin
  perform setseed(0.37);                                       -- 같은 모양의 데이터가 나오도록 난수 고정
-- 주문·추천 기록은 회원이 지워지면 연결만 끊기므로 회원보다 먼저 지운다 (주문 상세·구성은 함께 지워짐)
  delete from orders where member_id in (select id from members where kakao_id like 'sample-%');
  delete from recommendation_events where member_id in (select id from members where kakao_id like 'sample-%');
  delete from staff_calls where done_at is not null;
  delete from sms_logs where content like '[샘플]%';               -- 수신자(sms_log_recipients)도 함께 지워짐
  delete from alerts where title like '[샘플]%';
  delete from external_context where event_text like '[샘플]%';
  delete from members where kakao_id like 'sample-%';             -- 로그인 기록·쿠폰도 함께 지워짐

  -- 1) 고객 40명: 1~10 단골 후보, 11~22 재방문, 23~32 신규, 33~40 휴면(두 달 넘게 안 옴)
  for i in 1..40 loop
    insert into members (kakao_id, nickname, phone, gender, birthday, birth_year,
                         marketing_consent, marketing_consent_at, opted_out, opted_out_at)
    values ('sample-' || lpad(i::text, 3, '0'),
            '[샘플] ' || v_names[(i - 1) % 20 + 1] || case when i > 20 then ' ' || i else '' end,
            case when i % 13 = 0 then null else '010-0000-' || lpad(i::text, 4, '0') end,   -- 가짜 번호, 일부는 번호 없음
            case when i % 2 = 0 then 'female' else 'male' end,
            lpad((1 + i % 12)::text, 2, '0') || lpad((1 + i % 28)::text, 2, '0'),
            1985 + i % 20,
            i % 10 not in (3, 6, 9),                                                          -- 약 70% 문자 수신 동의
            case when i % 10 not in (3, 6, 9) then now() - interval '40 days' end,
            i % 10 = 2 and i <= 32,                                                           -- 4명은 수신거부
            case when i % 10 = 2 and i <= 32 then now() - interval '5 days' end)
    returning id into v_id;
    mids := mids || v_id;
  end loop;

  -- 2) 회원별 로그인(방문) 기록 + 룰렛 + 쿠폰 + 주문 (방문 횟수는 로그인 횟수와 맞춘다)
  for i in 1..40 loop
    target  := case when i <= 10 then 5 + i % 8 when i <= 22 then 2 + i % 3 when i <= 32 then 1 else 1 + i % 4 end;
    lastoff := case when i <= 32 then i % 7 else 61 + i % 25 end;          -- 마지막 방문이 며칠 전인지
    gap     := case when i <= 32 then greatest(1, floor((28 - lastoff)::numeric / target)::int) else 2 end;
    for k in 1..target loop
      d := v_today - (lastoff + (k - 1) * gap);                            -- 같은 회원은 하루에 한 번만 로그인
      v_login := least(((d + make_interval(hours => 17 + floor(random() * 6)::int,
                                           mins => floor(random() * 60)::int)) at time zone 'Asia/Seoul'),
                       now() - interval '30 minutes');                     -- 저녁 17~22시 위주, 미래 시각은 피함
      v_tn := 1 + floor(random() * 30)::int;
      insert into table_logins (table_no, member_id, login_day, logged_in_at, roulette_eligible)
      values (v_tn, mids[i], d, v_login, true) returning id into v_tl;

      -- 룰렛: 약 60%가 돌리고, 당첨은 쿠폰함에 쿠폰으로 들어간다(안내문은 사본으로 저장)
      v_cid := null;
      if random() < 0.6 then
        select * into v_prize from roulette_prizes order by random() limit 1;
        update table_logins set prize_id = v_prize.id, prize_text = v_prize.short_text,
               played_at = v_login + interval '2 minutes' where id = v_tl;
        insert into coupons (member_id, table_login_id, table_no, prize_id, kind, label, emoji, percent, menu_id, issued_at)
        values (mids[i], v_tl, v_tn, v_prize.id, v_prize.kind, v_prize.short_text, v_prize.emoji,
                v_prize.percent, v_prize.menu_id, v_login + interval '2 minutes')
        returning id into v_cid;
      end if;
      v_used := v_cid is not null and random() < 0.4;                      -- 쿠폰 약 40%는 주문에 사용

      -- 주문: 로그인의 약 90% (쿠폰을 쓴 로그인은 반드시)
      if v_used or random() < 0.9 then
        v_ai := random() < 0.25;                                           -- 약 25%는 AI 추천 조합 주문
        v_evt := null;
        if v_ai then
          select jsonb_object_agg(q.id, (select o.value from quiz_options o where o.question_id = q.id order by random() limit 1))
            into v_ans from quiz_questions q;
          select code into v_w from weather_types order by random() limit 1;
          select array_agg(s.id) into v_combo from (
            select m.id from menus m join categories c on c.id = m.category_id
            where m.set_ok and not c.is_virtual and not m.is_soldout order by random() limit 3) s;
          insert into recommendation_events (table_no, member_id, answers, hour, weather_code, combo_ids, created_at)
          values (v_tn, mids[i], v_ans, extract(hour from v_login at time zone 'Asia/Seoul')::int, v_w, v_combo,
                  v_login + interval '10 minutes')
          returning id into v_evt;
        end if;

        insert into orders (table_no, member_id, total, ai_combo, recommendation_event_id, created_at)
        values (v_tn, mids[i], 0, v_ai, v_evt, v_login + interval '15 minutes') returning id into v_oid;

        if v_ai then                                                       -- 조합 한 줄(10% 할인) + 구성 메뉴
          select sum(price) into v_sum from menus where id = any(v_combo);
          insert into order_items (order_id, menu_id, kind, name, unit_price, original_unit_price, qty)
          values (v_oid, null, 'combo', 'AI 추천 조합', (v_sum * 90 / 100) / 10 * 10, v_sum, 1) returning id into v_iid;
          insert into order_item_components (order_item_id, menu_id, name, qty)
          select v_iid, id, name, 1 from menus where id = any(v_combo);
        end if;

        n := case when v_ai then floor(random() * 3)::int else 1 + floor(random() * 4)::int end;   -- 일반 메뉴 줄 수
        for it in select m.id, m.name, m.price from menus m join categories c on c.id = m.category_id
                  where not c.is_virtual and not m.is_soldout order by random() limit n loop
          insert into order_items (order_id, menu_id, kind, name, unit_price, qty)
          values (v_oid, it.id, 'menu', it.name, it.price, 1 + floor(random() * 3)::int);
        end loop;

        v_pct := 0;
        if v_used then
          if v_prize.kind = 'free' then                                    -- 서비스 쿠폰: 0원 줄 추가
            insert into order_items (order_id, menu_id, kind, name, unit_price, qty)
            select v_oid, m.id, 'roulette_service', m.name, 0, 1 from menus m where m.id = v_prize.menu_id;
          else
            v_pct := v_prize.percent;                                      -- 할인 쿠폰: 총액에 할인율 적용
          end if;
          update coupons set used_at = v_login + interval '15 minutes', used_order_id = v_oid where id = v_cid;
        end if;
        select coalesce(sum(unit_price * qty), 0) into v_sub from order_items where order_id = v_oid;
        update orders set total = ((v_sub * (100 - v_pct) / 100) / 10 * 10)::int, roulette_discount_percent = v_pct
         where id = v_oid;
      end if;
    end loop;
  end loop;

  -- 방문 횟수·마지막 방문·가입일을 실제 로그인 기록에 맞춘다
  update members m set visit_count = c.cnt, last_visit_at = c.last_at, created_at = c.first_at
  from (select member_id, count(*) cnt, max(logged_in_at) last_at, min(logged_in_at) first_at
          from table_logins where member_id = any(mids) group by member_id) c
  where m.id = c.member_id;

  -- 3) 주문으로 이어지지 않은 AI 추천 노출 25건
  for k in 1..25 loop
    select jsonb_object_agg(q.id, (select o.value from quiz_options o where o.question_id = q.id order by random() limit 1))
      into v_ans from quiz_questions q;
    select code into v_w from weather_types order by random() limit 1;
    select array_agg(s.id) into v_combo from (
      select m.id from menus m join categories c on c.id = m.category_id
      where m.set_ok and not c.is_virtual and not m.is_soldout order by random() limit 3) s;
    insert into recommendation_events (table_no, member_id, answers, hour, weather_code, combo_ids, created_at)
    values (1 + floor(random() * 30)::int, mids[1 + floor(random() * 40)::int], v_ans, 18 + k % 5, v_w, v_combo,
            now() - make_interval(days => floor(random() * 28)::int, hours => floor(random() * 5)::int));
  end loop;

  -- 4) 직원 호출 40건 (최근 14일). done_at 을 채워 샘플 표시로 쓴다
  for k in 1..40 loop
    insert into staff_calls (table_no, items, created_at, done_at)
    select 1 + floor(random() * 30)::int,
           (select array_agg(label) from (select label from staff_call_items order by random() limit 1 + k % 2) s),
           x.t, x.t + interval '3 minutes'
    from (select now() - make_interval(days => floor(random() * 14)::int, hours => floor(random() * 6)::int, mins => k) as t) x;
  end loop;

  -- 5) 문자 이력 6건 (지난달 2 + 이번 달 4). 수신자는 발송 가능한 샘플 회원 중에서 뽑는다
  for r in select * from (values
      (35, 'SMS', 12, 'sent',    '[샘플] 단골 고객님, 이번 주말 생맥주 1+1 이벤트를 진행합니다!'),
      (33, 'LMS',  6, 'sent',    '[샘플] 추석 연휴 영업시간 안내와 재방문 감사 쿠폰을 알려드립니다. 많은 방문 부탁드립니다.'),
      ( 9, 'SMS', 10, 'dry_run', '[샘플] 오랜만이에요! 이번 주 방문하시면 안주 서비스를 드려요.'),
      ( 6, 'LMS',  8, 'dry_run', '[샘플] 가을 신메뉴 출시 안내: 매콤 닭발과 어묵탕을 만나보세요. 방문 시 룰렛 이벤트도 진행합니다.'),
      ( 3, 'SMS',  8, 'sent',    '[샘플] 비 오는 날엔 파전에 막걸리! 오늘 저녁 방문 고객 10% 할인.'),
      ( 1, 'SMS',  5, 'failed',  '[샘플] 단골 감사 이벤트 안내 (발송 실패 예시)')
    ) as t(days_ago, typ, cnt, st, body) loop
    insert into sms_logs (created_at, month, request_id, type, content, target_count, status, error)
    values (now() - make_interval(days => r.days_ago),
            to_char((now() - make_interval(days => r.days_ago)) at time zone 'Asia/Seoul', 'YYYY-MM'),
            case when r.st = 'sent' then 'sample-req-' || r.days_ago end, r.typ, r.body, r.cnt, r.st,
            case when r.st = 'failed' then '발송 실패(샘플)' end)
    returning id into v_log;
    insert into sms_log_recipients (log_id, member_id)
    select v_log, v.id from v_members_graded v
    where v.kakao_id like 'sample-%' and v.sms_sendable order by random() limit r.cnt;
  end loop;

  -- 6) 알림 5건 (휴면 고객 3 + 품절 2) 과 오늘의 날씨·행사 문구
  for i in 33..35 loop
    insert into alerts (kind, title, detail, member_id, created_at)
    select 'dormant', '[샘플] 휴면 고객 알림', nickname || ' 님이 60일 넘게 방문하지 않았어요.', id, now() - make_interval(days => i - 30)
    from members where id = mids[i];
  end loop;
  insert into alerts (kind, title, detail, menu_id, created_at, acknowledged_at)
  select 'soldout', '[샘플] 품절 알림', name || ' 메뉴가 품절로 표시됐어요.', id, now() - interval '2 days',
         case when row_number() over (order by id) = 2 then now() - interval '1 day' end
  from (select id, name from menus order by sort_order limit 2) m;
  insert into external_context (day, weather_text, event_text)
  values (v_today, '맑고 선선한 가을 저녁', '[샘플] 홍대 거리 버스킹 공연이 있는 날')
  on conflict (day) do nothing;
end $$;
