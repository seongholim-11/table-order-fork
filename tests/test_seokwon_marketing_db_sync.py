"""석원: 실제 API에 연결한 성과 화면과 추천 문자 대상의 DB 갱신을 확인한다."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'backend'), str(ROOT / 'admin')]

import admin_repository as ar
from admin.views import marketing
from test_sooyong_today_orders import open_dashboard, server


def test_growth_screen_refresh_reads_new_members_and_guest_sales(server, monkeypatch):
    """한 화면에서 새 주문을 반영하고, 대시보드 중복 없이 성장 성과를 다시 계산한다."""
    now = datetime.now(timezone.utc)
    db = server.app.state.db
    member = server.app.state.members.upsert_login('growth-sync', '성과 검증 고객')
    for days, amount, ai in ((2, 10000, False), (0, 20000, True)):
        db.run('INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (7, ?, ?, ?, ?)',
               (member['id'], amount, ai, (now - timedelta(days=days)).isoformat()))
    screen = open_dashboard(monkeypatch)
    screen.sidebar.radio(key='nav_sub_마케팅').set_value('F&B그로스 성과').run()
    assert not screen.exception
    html = '\n'.join(element.value for element in screen.get('html'))
    assert 'AI 도입 후 월환산 성과 매출</div><div class="v">600,000' in html
    server.app.state.members.upsert_login('growth-new', '새 고객')
    db.run('INSERT INTO orders (table_no, total, ai_combo, created_at) VALUES (8, 30000, 0, ?)', (now.isoformat(),))
    screen.button(key='growth_refresh').click().run()
    assert not screen.exception
    html = '\n'.join(element.value for element in screen.get('html'))
    assert 'AI 도입 후 월환산 성과 매출</div><div class="v">1,500,000' in html
    assert '최종 월환산 매출 차이</div><div class="v">1,350,000' in html
    # AI 조합 매출은 동일하고 일반 주문만 늘었으므로 그 비중은 100%에서 40%로 바뀐다.
    assert '도입 후 AI 주문 매출 비중</div><div class="v">40.0%' in html
    assert '1. 매출데이터' not in html and '2. 고객데이터' not in html


def test_recommendation_sms_does_not_auto_select_new_db_members(server, monkeypatch):
    """추천을 고른 후 DB에 추가된 회원은 사장님이 체크하기 전까지 자동 발송 대상으로 넣지 않는다."""
    def add_member(key):
        member = server.app.state.members.upsert_login(key, key, phone='01000000000')
        server.app.state.members.set_marketing_consent(member['id'], True)
        return member['id']

    chosen = add_member('추천 대상')
    repo = ar.AdminRepository(ar.ApiBackend('admin-secret'))
    state = {'grade_rule': repo.customer_grade_rules()}
    monkeypatch.setattr(marketing, 'ss', state)
    monkeypatch.setattr(marketing.st, 'query_params', {})
    marketing.execute_sms_recommendation(repo, {'member_ids': [chosen], 'target_grades': ['신규'],
                                               'title': '신규 추천', 'action': '감사 인사', 'sms_body': '감사합니다'})
    newcomer = add_member('나중에 가입')
    monkeypatch.setattr(marketing.st, 'data_editor', lambda rows, **kwargs: rows)
    selected = marketing.recipient_editor(repo.members(), ['신규'])
    assert selected == [chosen]
    assert repo.sms_preview(['신규'], '감사합니다', member_ids=selected)['targets'] == 1

    # 직접 체크한 추가 대상은 다음 화면 실행에서도 유지한다.
    def check_new_member(rows, **kwargs):
        rows.loc[rows['customer_id'] == newcomer, '발송'] = True
        return rows

    monkeypatch.setattr(marketing.st, 'data_editor', check_new_member)
    assert set(marketing.recipient_editor(repo.members(), ['신규'])) == {chosen, newcomer}
    monkeypatch.setattr(marketing.st, 'data_editor', lambda rows, **kwargs: rows)
    assert set(marketing.recipient_editor(repo.members(), ['신규'])) == {chosen, newcomer}
    # 실제 수신거부는 화면 선택과 무관하게 서버가 최종 제외해야 한다.
    server.app.state.members.opt_out(chosen)
    assert repo.sms_preview(['신규'], '감사합니다', member_ids=[chosen, newcomer])['targets'] == 1
