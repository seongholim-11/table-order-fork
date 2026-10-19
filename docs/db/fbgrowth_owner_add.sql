-- 사장님 계정 등록 (Supabase SQL Editor 에서 실행)
-- 1) Supabase 대시보드 > Authentication > Users > Add user 로 이메일/비밀번호 계정을 먼저 만든다.
-- 2) 아래 이메일을 그 계정 이메일로 바꿔 실행하면 owners 에 등록되어 관리자 화면에 로그인할 수 있다.
insert into owners (user_id)
select id from auth.users where email = 'owner@example.com'
on conflict (user_id) do nothing;
