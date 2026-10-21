-- F&BGrowth 테이블·컬럼 코멘트 (docs/설계/DB_설계.md 의 컬럼 사전과 같은 내용)
-- Supabase SQL Editor에서 실행합니다. 코멘트만 바꾸며 데이터·구조는 건드리지 않고, 여러 번 실행해도 안전합니다.

comment on table public.store_info is '매장 정보(매장 1개, 한 행만 허용)';
comment on column public.store_info.id is '고정 키. 한 행만 허용';
comment on column public.store_info.name is '매장 이름';
comment on column public.store_info.branch is '지점명';
comment on column public.store_info.slogan is '손님 시작 화면 슬로건';
comment on column public.store_info.tables is '매장 전체 테이블 수. QR의 ?table= 번호 검증에 사용';

comment on table public.categories is '메뉴 카테고리';
comment on column public.categories.id is '카테고리 식별자(예: chicken, ai, best)';
comment on column public.categories.name is '카테고리 이름. 중복 불가';
comment on column public.categories.icon is '아이콘 이모지';
comment on column public.categories.color_from is '카드 그라데이션 시작색(#RRGGBB)';
comment on column public.categories.color_to is '카드 그라데이션 끝색';
comment on column public.categories.is_virtual is '가상 카테고리 여부(ai·best는 메뉴를 직접 넣지 않음)';
comment on column public.categories.sort_order is '화면 정렬 순서';

comment on table public.menus is '메뉴';
comment on column public.menus.id is '메뉴 식별자(예: c1)';
comment on column public.menus.category_id is '소속 카테고리. 가상 카테고리는 트리거로 거부';
comment on column public.menus.name is '메뉴 이름';
comment on column public.menus.description is '설명';
comment on column public.menus.price is '가격(원)';
comment on column public.menus.emoji is '이모지(사진이 없을 때 표시)';
comment on column public.menus.tags is '태그 목록(예: BEST, 매운맛)';
comment on column public.menus.is_soldout is '품절 여부';
comment on column public.menus.spicy is '매운맛 단계(0 안 매움~3 아주 매움)';
comment on column public.menus.weight is 'AI 추천 가중치';
comment on column public.menus.set_ok is 'AI 추천 세트에 넣을 수 있는지';
comment on column public.menus.image_url is '메뉴 사진 주소';
comment on column public.menus.sort_order is '카테고리 안 정렬 순서';
comment on column public.menus.created_at is '등록 시각';
comment on column public.menus.updated_at is '수정 시각(트리거가 자동 갱신)';
comment on column public.menus.is_event is '이벤트(룰렛 서비스) 메뉴 후보 여부';

comment on table public.members is '카카오 로그인 회원(손님)';
comment on column public.members.id is '회원 번호';
comment on column public.members.kakao_id is '카카오 회원 식별자';
comment on column public.members.auth_user_id is 'Supabase Auth 로그인 연결(선택)';
comment on column public.members.nickname is '카카오 닉네임';
comment on column public.members.phone is '휴대폰 번호(문자 발송용, 평문)';
comment on column public.members.gender is '성별';
comment on column public.members.birthday is '카카오가 주는 생일 원문(MMDD 등)';
comment on column public.members.birth_year is '출생연도(연령대 통계)';
comment on column public.members.marketing_consent is '광고 문자 수신 동의';
comment on column public.members.marketing_consent_at is '동의 시각';
comment on column public.members.opted_out is '수신거부(동의보다 우선)';
comment on column public.members.opted_out_at is '수신거부 시각';
comment on column public.members.visit_count is '방문 횟수(로그인할 때마다 +1)';
comment on column public.members.last_visit_at is '마지막 방문(로그인) 시각';
comment on column public.members.created_at is '가입 시각';

comment on table public.login_sessions is 'QR 로그인 진행 상태(서버 미사용)';
comment on column public.login_sessions.id is '세션 식별자';
comment on column public.login_sessions.token is 'QR에 들어가는 값(휴대폰용)';
comment on column public.login_sessions.secret is '태블릿만 아는 값(폴링·WebSocket 인증)';
comment on column public.login_sessions.table_no is '로그인하는 테이블 번호';
comment on column public.login_sessions.status is '진행 상태';
comment on column public.login_sessions.member_id is '로그인 완료한 회원';
comment on column public.login_sessions.blocked_member_ids is '이 태블릿에서 이미 로그인한 회원(중복 차단)';
comment on column public.login_sessions.marketing_consent is '휴대폰에서 체크한 수신 동의';
comment on column public.login_sessions.pkce_verifier is '카카오 PKCE 검증값';
comment on column public.login_sessions.claimed is '태블릿이 결과를 이미 받아갔는지';
comment on column public.login_sessions.created_at is '발급 시각';
comment on column public.login_sessions.expires_at is '만료 시각';

comment on table public.roulette_prizes is '룰렛 칸 구성';
comment on column public.roulette_prizes.id is '칸 번호';
comment on column public.roulette_prizes.label is '칸에 보이는 문구';
comment on column public.roulette_prizes.short_text is '당첨 안내문';
comment on column public.roulette_prizes.emoji is '이모지';
comment on column public.roulette_prizes.color is '칸 색';
comment on column public.roulette_prizes.kind is '할인 칸 / 서비스 메뉴 칸';
comment on column public.roulette_prizes.percent is '할인율(할인 칸만)';
comment on column public.roulette_prizes.menu_id is '무료 메뉴(서비스 칸만)';
comment on column public.roulette_prizes.weight is '당첨 확률 가중치';
comment on column public.roulette_prizes.sort_order is '칸 순서';

comment on table public.table_logins is '테이블 로그인 이력과 룰렛 참여·당첨';
comment on column public.table_logins.id is '기록 번호';
comment on column public.table_logins.table_no is '테이블 번호';
comment on column public.table_logins.member_id is '로그인한 회원';
comment on column public.table_logins.login_day is '로그인 날짜(KST). 하루 1회 규칙의 기준';
comment on column public.table_logins.logged_in_at is '로그인 시각. 테이블 누적 주문 기준 시각';
comment on column public.table_logins.roulette_eligible is '룰렛 기회가 있는지(처음 로그인한 회원만)';
comment on column public.table_logins.prize_id is '당첨된 칸';
comment on column public.table_logins.prize_text is '당첨 안내문 사본(칸이 바뀌어도 기록 유지)';
comment on column public.table_logins.played_at is '룰렛을 돌린 시각(null이면 아직 안 돌림)';

comment on table public.coupons is '쿠폰함(룰렛 당첨 쿠폰)';
comment on column public.coupons.id is '쿠폰 번호';
comment on column public.coupons.member_id is '쿠폰 주인';
comment on column public.coupons.table_login_id is '발급 근거 룰렛 기록(룰렛 1회당 쿠폰 1장)';
comment on column public.coupons.table_no is '받은 테이블';
comment on column public.coupons.prize_id is '당첨된 칸';
comment on column public.coupons.kind is '할인 / 서비스 쿠폰';
comment on column public.coupons.label is '안내문 사본(칸이 바뀌어도 유지)';
comment on column public.coupons.emoji is '이모지';
comment on column public.coupons.percent is '할인율(할인 쿠폰만)';
comment on column public.coupons.menu_id is '서비스 쿠폰의 무료 메뉴';
comment on column public.coupons.issued_at is '발급 시각';
comment on column public.coupons.expires_at is '유효기간(정책 미정, null=없음)';
comment on column public.coupons.used_at is '사용 시각(null이면 사용 가능)';
comment on column public.coupons.used_order_id is '쿠폰을 사용한 주문';

comment on table public.orders is '주문 헤더';
comment on column public.orders.id is '주문번호';
comment on column public.orders.table_no is '주문한 테이블';
comment on column public.orders.member_id is '회원(비회원은 null)';
comment on column public.orders.total is '할인 반영 후 결제 금액(원)';
comment on column public.orders.roulette_discount_percent is '이 주문에 적용된 쿠폰 할인율';
comment on column public.orders.ai_combo is 'AI 추천 조합이 포함된 주문인지';
comment on column public.orders.recommendation_event_id is '주문의 바탕이 된 추천 노출 기록';
comment on column public.orders.created_at is '주문 시각';

comment on table public.order_items is '주문 줄';
comment on column public.order_items.id is '줄 번호';
comment on column public.order_items.order_id is '소속 주문';
comment on column public.order_items.menu_id is '메뉴(조합 줄은 null)';
comment on column public.order_items.kind is '일반 메뉴 / AI 조합 / 룰렛 서비스';
comment on column public.order_items.name is '주문 시점 이름 사본';
comment on column public.order_items.option_label is '옵션 문구(예: 맵기 단계)';
comment on column public.order_items.unit_price is '주문 시점 단가';
comment on column public.order_items.original_unit_price is '조합 할인 전 단가';
comment on column public.order_items.qty is '수량';

comment on table public.order_item_components is 'AI 조합 줄의 구성 메뉴';
comment on column public.order_item_components.id is '구성 번호';
comment on column public.order_item_components.order_item_id is '소속 주문 줄';
comment on column public.order_item_components.menu_id is '구성 메뉴';
comment on column public.order_item_components.name is '주문 시점 이름 사본';
comment on column public.order_item_components.option_label is '옵션 문구';
comment on column public.order_item_components.qty is '구성 수량';

comment on table public.recommendation_events is 'AI 추천 노출 기록(적중률 분모)';
comment on column public.recommendation_events.id is '기록 번호';
comment on column public.recommendation_events.table_no is '테이블 번호';
comment on column public.recommendation_events.member_id is '회원(비회원은 null)';
comment on column public.recommendation_events.answers is '손님 답변(people·budget·spicy·hunger·stress·kind·intent·gender)';
comment on column public.recommendation_events.hour is '추천 당시 시각(시)';
comment on column public.recommendation_events.weather_code is '추천 당시 날씨 코드';
comment on column public.recommendation_events.combo_ids is '보여 준 추천 조합 id 목록';
comment on column public.recommendation_events.created_at is '노출 시각';

comment on table public.staff_call_items is '직원 호출 항목(물·수저 등)';
comment on column public.staff_call_items.id is '항목 번호';
comment on column public.staff_call_items.label is '항목 이름';
comment on column public.staff_call_items.sort_order is '화면 정렬 순서';

comment on table public.staff_calls is '직원 호출 기록';
comment on column public.staff_calls.id is '호출 번호';
comment on column public.staff_calls.table_no is '호출한 테이블';
comment on column public.staff_calls.items is '요청 항목 목록';
comment on column public.staff_calls.created_at is '호출 시각';
comment on column public.staff_calls.done_at is '처리 완료 시각';

comment on table public.service_tip_checks is '손님 응대 제안 확인 기록';
comment on column public.service_tip_checks.member_id is '손님';
comment on column public.service_tip_checks.order_id is '제안의 근거 주문';
comment on column public.service_tip_checks.checked_at is '확인한 시각(행이 있으면 확인됨)';

comment on table public.quiz_questions is 'AI 추천 질문';
comment on column public.quiz_questions.id is '질문 식별자(hunger, stress, people, gender, kind, spicy, intent, budget)';
comment on column public.quiz_questions.group_name is '질문 묶음 이름';
comment on column public.quiz_questions.title is '질문 문구';
comment on column public.quiz_questions.sort_order is '질문 순서';

comment on table public.quiz_options is 'AI 추천 질문의 보기';
comment on column public.quiz_options.id is '보기 번호';
comment on column public.quiz_options.question_id is '소속 질문';
comment on column public.quiz_options.value is '보기 값(서버가 쓰는 코드)';
comment on column public.quiz_options.label is '보기 문구';
comment on column public.quiz_options.emoji is '이모지';
comment on column public.quiz_options.sort_order is '보기 순서';

comment on table public.weather_types is '날씨 종류 정의';
comment on column public.weather_types.code is '날씨 코드(sunny, cloudy, rain, snow, hot)';
comment on column public.weather_types.label is '화면 표시 이름';
comment on column public.weather_types.icon is '아이콘 이모지';

comment on table public.weather_current is '현재 날씨(한 행)';
comment on column public.weather_current.id is '고정 키. 한 행만 허용';
comment on column public.weather_current.code is '현재 날씨 코드';
comment on column public.weather_current.source is '값의 출처(dummy 또는 외부 날씨 API)';
comment on column public.weather_current.updated_at is '갱신 시각';

comment on table public.recommendation_rules is '추천 규칙(키별 JSON)';
comment on column public.recommendation_rules.key is '규칙 이름(discount_percent, pairings, drinks, pair_meta 등)';
comment on column public.recommendation_rules.value is '규칙 내용';
comment on column public.recommendation_rules.updated_at is '수정 시각';

comment on table public.owners is '관리자(사장님) 계정 허용 목록';
comment on column public.owners.user_id is 'Supabase Auth 사용자';
comment on column public.owners.role is '권한(사장님 한 종류)';
comment on column public.owners.created_at is '등록 시각';

comment on table public.app_settings is '설정 값(key-value)';
comment on column public.app_settings.key is '설정 이름(grade_rule, sms_limits 등)';
comment on column public.app_settings.value is '설정 내용';
comment on column public.app_settings.updated_at is '수정 시각';

comment on table public.alerts is '운영 알림(서버 미사용)';
comment on column public.alerts.id is '알림 번호';
comment on column public.alerts.kind is '알림 종류';
comment on column public.alerts.title is '제목';
comment on column public.alerts.detail is '내용';
comment on column public.alerts.member_id is '관련 회원';
comment on column public.alerts.menu_id is '관련 메뉴';
comment on column public.alerts.created_at is '생성 시각';
comment on column public.alerts.acknowledged_at is '확인 시각(null이면 미확인)';

comment on table public.sms_logs is '문자 발송·예약 기록';
comment on column public.sms_logs.id is '기록 번호';
comment on column public.sms_logs.created_at is '기록 시각';
comment on column public.sms_logs.month is '''YYYY-MM''. 월 한도 집계 기준';
comment on column public.sms_logs.request_id is '솔라피 요청 ID';
comment on column public.sms_logs.type is '문자 종류';
comment on column public.sms_logs.content is '발송 본문';
comment on column public.sms_logs.target_count is '대상 인원 수';
comment on column public.sms_logs.status is '발송 상태';
comment on column public.sms_logs.error is '실패 사유';
comment on column public.sms_logs.scheduled_at is '예약 발송 시각';

comment on table public.sms_log_recipients is '문자 수신 회원(서버 미사용)';
comment on column public.sms_log_recipients.log_id is '발송 기록';
comment on column public.sms_log_recipients.member_id is '수신 회원';

comment on table public.external_context is '오늘 날씨·지역 행사 문구(AI 문자 후보용)';
comment on column public.external_context.day is '날짜';
comment on column public.external_context.weather_text is '날씨 문구';
comment on column public.external_context.event_text is '지역 행사 문구';
comment on column public.external_context.updated_at is '수정 시각';

comment on table public.chat_sessions is '챗봇 대화방';
comment on column public.chat_sessions.id is '대화방 식별자';
comment on column public.chat_sessions.owner_id is '대화방 주인(사장님)';
comment on column public.chat_sessions.title is '대화방 제목';
comment on column public.chat_sessions.created_at is '생성 시각';
comment on column public.chat_sessions.updated_at is '수정 시각(트리거가 자동 갱신)';

comment on table public.chat_messages is '챗봇 메시지';
comment on column public.chat_messages.id is '메시지 번호';
comment on column public.chat_messages.session_id is '소속 대화방';
comment on column public.chat_messages.role is '말한 쪽';
comment on column public.chat_messages.content is '메시지 본문';
comment on column public.chat_messages.created_at is '작성 시각';
