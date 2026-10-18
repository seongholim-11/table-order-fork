"""석원: 실제 DB 행의 추가·변경이 마케팅의 각 조회에 함께 반영되는지 검증한다."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.chat import ChatService
from app.services.grades import GRADES, KST
from app.stores.stats import StatsStore
from shared.opportunity_engine import build_context
from tests.conftest import ADMIN, settings


def get(client, path):
    response = client.get('/admin/api/' + path, headers=ADMIN)
    assert response.status_code == 200, response.text
    return response.json()


def test_thousand_members_and_orders_update_every_marketing_reader(client):
    """운영 DB 대신 격리된 DB에 1,000명과 회원·비회원 주문 1,000건을 넣는다."""
    db = client.app.state.db
    now = datetime.now(KST)
    assert get(client, 'members')['members'] == []
    assert get(client, 'marketing/growth-performance')['empty']
    ids = []
    for index in range(1000):
        member_id = db.run(
            'INSERT INTO members (kakao_id, nickname, phone, marketing_consent, visit_count, last_visit_at, created_at) '
            'VALUES (?, ?, ?, 1, 3, ?, ?)',
            (f'sync-{index}', f'검증회원{index}', '01000000000' if index % 2 == 0 else None,
             now.isoformat(), now.isoformat()))
        ids.append(member_id)
        stamp = now - timedelta(days=2 if index < 500 else 0)
        amount = 10000 if index < 500 else 20000
        order_id = db.run('INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (7, ?, ?, ?, ?)',
                         (None if index % 5 == 0 else member_id, amount, index >= 500 and index % 2 == 0,
                          stamp.astimezone(timezone.utc).isoformat()))
        db.run("INSERT INTO order_items (order_id, menu_id, kind, name, unit_price, qty) VALUES (?, 'a4', 'menu', '계란말이', ?, 1)",
               (order_id, amount))

    def verify(member_count, order_count, revenue, today_revenue, sendable):
        assert len(get(client, 'members')['members']) == member_count
        grades = get(client, 'customers/grades')
        assert sum(grades[g] for g in GRADES) == member_count
        summary = get(client, 'marketing/opportunities')['summary']
        assert summary['members']['total'] == member_count
        assert summary['members']['sendable'] == sendable
        assert summary['orders']['count'] == order_count
        assert summary['orders']['revenue'] == revenue
        insights = get(client, 'stats/insights')
        assert insights['revenue'] == revenue
        assert insights['today_revenue'] == today_revenue
        assert insights['member_revenue'] + insights['guest_revenue'] == today_revenue
        assert sum(insights['by_hour'].values()) == sum(insights['by_weekday'].values()) == revenue
        stats = get(client, 'stats')
        assert stats['today_orders'] == order_count - 500
        assert stats['avg_order_amount'] == today_revenue // (order_count - 500)
        growth = get(client, 'marketing/growth-performance')
        assert growth['observed_post_revenue'] == today_revenue
        assert sum(row['revenue'] for row in growth['sales_timeline']) == revenue
        assert growth['performance_monthly'] == today_revenue * 30
        assert growth['monthly_growth'] == growth['performance_monthly'] - growth['baseline_monthly']
        # 발송은 하지 않고, 실제 문자 미리보기와 후보 생성의 원자료를 대조한다.
        preview = client.post('/admin/api/marketing/sms/preview', headers=ADMIN,
                              json={'grades': GRADES, 'body': '검증 문구'}).json()
        assert preview['targets'] == sendable
        assert sum(client.app.state.sms_candidates.summary()['pool'].values()) == sendable
        chat = ChatService(settings(), StatsStore(db), client.app.state.members).summary(now.date())
        assert f'전체 회원 {member_count}명' in chat
        assert f'전체 누적: 매출 {revenue:,}원, 주문 {order_count}건' in chat

    verify(1000, 1000, 15000000, 10000000, 500)
    assert len(get(client, 'marketing/regular-preferences')['preferences']) == 400
    # 같은 앱 인스턴스를 유지한 채 고객·주문을 추가하고 기존 회원의 수신거부를 변경한다.
    member = client.app.state.members.upsert_login('sync-new', '새고객', phone='01000000000')
    client.app.state.members.set_marketing_consent(member['id'], True)
    client.app.state.members.opt_out(ids[0])
    db.run('INSERT INTO orders (table_no, member_id, total, ai_combo, created_at) VALUES (17, ?, 30000, 1, ?)',
           (member['id'], now.isoformat()))
    verify(1001, 1001, 15030000, 10030000, 500)
    # 가격 수정과 회원 수신거부 취소도 새 요청에 반영돼야 한다.
    db.run('UPDATE orders SET total=total+1000 WHERE id=1000')
    client.app.state.members.set_marketing_consent(ids[0], True)
    verify(1001, 1001, 15031000, 10031000, 501)


@pytest.mark.parametrize('stamp', ['2026-10-16T15:30:00Z', '2026-10-16 15:30:00',
                                  '2026-10-17T00:30:00+09:00', datetime(2026, 10, 16, 15, 30)])
def test_recommendation_hour_weekday_follow_kst(stamp):
    """동일한 토요일 새벽 주문을 UTC·KST·시간대 없는 DB 표현으로 각각 입력한다."""
    context = build_context([], [{'ts': stamp, 'total': 10000}], [], {}, datetime(2026, 10, 17).date())
    assert context['orders']['peak_hours'] == [0]
    assert context['orders']['weekdays'] == [(5, 1)]
