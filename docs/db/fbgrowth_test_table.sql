-- 개발 흐름 확인용 `test` 테이블. 서비스 데이터는 담지 않는다.
-- Supabase `table-order` 프로젝트에는 2026-10-16 에 이미 적용했다. 여러 번 실행해도 안전하다.
create table if not exists test (
  id         text primary key,                 -- 서버가 만든 임의 id (uuid 문자열)
  value      text not null,                    -- 넣었다가 다시 읽어 비교하는 값
  created_at timestamptz not null default now()
);
-- 다른 테이블처럼 RLS 를 켠다. 정책이 없으므로 브라우저·anon 키는 접근할 수 없고 서버(DATABASE_URL)만 읽고 쓴다.
alter table test enable row level security;
