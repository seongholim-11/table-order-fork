-- 샘플 데이터 삭제 (fbgrowth_sample_data.sql 로 넣은 것만 지운다). 여러 번 실행해도 안전.
-- 구분 표시: 회원 kakao_id 'sample-%' / 알림·문자 '[샘플]' / 직원 호출 done_at 이 채워진 것(처리 기능이 없어 실제 데이터는 항상 null)
begin;
-- 주문·추천 기록은 회원이 지워지면 연결만 끊기므로 회원보다 먼저 지운다 (주문 상세·구성은 함께 지워짐)
delete from orders where member_id in (select id from members where kakao_id like 'sample-%');
delete from recommendation_events where member_id in (select id from members where kakao_id like 'sample-%');
delete from staff_calls where done_at is not null;
delete from sms_logs where content like '[샘플]%';               -- 수신자(sms_log_recipients)도 함께 지워짐
delete from alerts where title like '[샘플]%';
delete from external_context where event_text like '[샘플]%';
delete from members where kakao_id like 'sample-%';             -- 로그인 기록·쿠폰도 함께 지워짐
commit;
