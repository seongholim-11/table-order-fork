"""휴면 30일 표기와 DB 단골 주문율이 마케팅 AI 추천에만 나타나는지 확인한다."""

from datetime import datetime, timedelta, timezone

from test_sooyong_today_orders import open_dashboard, server
from app.services.grades import KST


def save_menu(server, menu_id, name, category="anju", price=14000):
    """테스트 메뉴도 메뉴 저장소를 통해 저장한다."""
    return server.app.state.shop.save_menu(
        menu_id, {"cat": category, "name": name, "price": price}
    )


def html_of(screen):
    return "\n".join(element.value for element in screen.get("html"))


def open_customers(monkeypatch):
    screen = open_dashboard(monkeypatch)
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert not screen.exception
    return screen


def open_recommendations(monkeypatch):
    screen = open_dashboard(monkeypatch)
    screen.sidebar.radio(key="nav_sub_마케팅").set_value("AI 추천").run()
    assert not screen.exception
    return screen


def prepare_history(server):
    """DB에만 있는 메뉴와 단골을 준비해 더미 문구가 표시되는 것을 방지한다."""
    db = server.app.state.db
    member = server.app.state.members.upsert_login("regular-screen", "주문 기억 손님")
    db.run("UPDATE members SET visit_count=5 WHERE id=?", (member["id"],))
    for menu_id, name in (("screen-fish", "DB 먹태"), ("screen-egg", "DB 계란말이")):
        save_menu(server, menu_id, name)
    for days in range(6):
        is_fish = days in (1, 2, 3, 4)
        at = datetime.now(timezone.utc) - timedelta(days=days)
        order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                       (7, member["id"], 14000, at.isoformat()))
        db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
               (order, "screen-fish" if is_fish else "screen-egg", "DB 먹태" if is_fish else "DB 계란말이", 1, 14000))
    return member


def test_dormant_label_thirty_days_filter_and_server_defaults(server, monkeypatch):
    member = server.app.state.members.upsert_login("human-screen", "31일 전 손님")
    server.app.state.db.run("UPDATE members SET visit_count=5, last_visit_at=? WHERE id=?",
                            ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(), member["id"]))
    screen = open_customers(monkeypatch)
    assert screen.multiselect[0].options == ["신규", "재방문", "단골", "휴면"]
    assert screen.dataframe[0].value.iloc[0]["등급"] == "휴면"
    assert "휴면 고객" in html_of(screen) and "휴먼" not in html_of(screen)
    screen.multiselect[0].set_value(["휴면"]).run()
    assert len(screen.dataframe[0].value) == 1
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("등급 분류 기준").run()
    assert not screen.exception
    assert screen.number_input(key="rule_dormant").value == 30
    assert "휴면" in screen.number_input(key="rule_dormant").label


def test_real_order_preference_evidence_and_rerecommend(server, monkeypatch):
    member = prepare_history(server)
    screen = open_recommendations(monkeypatch)
    assert "DB 먹태" in html_of(screen) and "오늘 주문: DB 계란말이" in html_of(screen)
    assert "5번째 방문" in html_of(screen) and "문구는 사장님 말투에 맞게" in html_of(screen)
    assert "오늘은 이런 멘트 어떠세요?" in html_of(screen) and "80% 이상" in html_of(screen)
    db = server.app.state.db
    order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                   (7, member["id"], 14000, datetime.now(timezone.utc).isoformat()))
    db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
           (order, "screen-fish", "DB 먹태", 1, 14000))
    # 재추천은 기존처럼 카드 묶음을 순환하며, 다시 나온 카드에는 새 DB 주문이 반영되어야 한다.
    for _ in range(4):
        screen.button(key="mk_rerecommend").click().run()
        assert not screen.exception
        if "오늘도 DB 먹태 주문이 확인" in html_of(screen):
            break
    assert "오늘도 DB 먹태 주문이 확인" in html_of(screen)


def test_empty_db_keeps_customer_screen_working(server, monkeypatch):
    screen = open_customers(monkeypatch)
    assert screen.dataframe[0].value.empty
    assert "단골 손님 대화 메모" not in [title.value for title in screen.subheader]
    screen.sidebar.radio(key="nav_sub_마케팅").set_value("AI 추천").run()
    assert not screen.exception and "주문율 80%" not in html_of(screen)
    # 실제 DB가 비어 있으면 시연용 손님 대신 빈 상태를 알려야 한다.
    assert 'class="recs regular-preferences"' not in html_of(screen)
    assert any("오늘 주문이 확인된 재방문 고객이 아직 없습니다" in element.value for element in screen.info)
    assert server.app.state.members.all() == []
    assert server.app.state.db.all("SELECT * FROM orders") == []


def test_customer_list_does_not_fetch_preferences(server, monkeypatch):
    import admin_repository as ar

    prepare_history(server)
    # 고객 목록에서 별도 메모를 만들거나 조회하지 않는 것을 확인한다.
    def unexpected_read(self):
        raise AssertionError("고객 화면이 마케팅 선호도를 조회했습니다.")

    monkeypatch.setattr(ar.AdminRepository, "regular_preferences", unexpected_read)
    screen = open_customers(monkeypatch)
    assert "단골 손님 대화 메모" not in [title.value for title in screen.subheader]


def test_three_db_examples_are_recommendation_cards(server, monkeypatch):
    from app.stores.regular_examples import seed_regular_examples

    db = server.app.state.db
    for menu_id, name in (("a1", "예시 먹태"), ("a2", "예시 골뱅이"), ("a4", "예시 계란말이"), ("a8", "예시 파전")):
        save_menu(server, menu_id, name)
    seed_regular_examples(db, datetime.now(KST).date())
    screen = open_recommendations(monkeypatch)
    html = html_of(screen)
    for nickname in ("[예시] 먹태 단골", "[예시] 계란말이 단골", "[예시] 파전 단골"):
        assert nickname in html
    assert "오늘 주문: 예시 골뱅이" in html
    assert "11번째 방문" in html and "멘트 예시" in html
    assert len({row["note"] for row in server.get("/admin/api/marketing/regular-preferences",
                                               headers={"Authorization": "Bearer admin-secret"}).json()["preferences"]}) > 1
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    assert addition.count('class="rec"') == 2
    assert "80% 이상" in addition and "90%" not in addition and "100%" not in addition
    # 기본 인사 세 명과 메뉴 취향 제안 한 명으로 나누어 비율 설명이 반복되지 않게 한다.
    assert addition.count("80% 이상") == 1
    assert "자주 드시는 메뉴를 기억하는 인사" in addition


def test_below_eighty_percent_still_shows_regular_without_claiming_preference(server, monkeypatch):
    import admin_repository as ar
    import marketing_ai
    from admin.marketing.recommendations import regular_preference_cards

    repo = ar.AdminRepository(ar.DummyBackend())
    ctx = marketing_ai.build_context(repo, ar.DEFAULT_RULE)
    original = marketing_ai.recommend(ctx)
    ctx["regular_preferences"] = [{"nickname": "조건 미달", "preference_rate": .79}]
    assert marketing_ai.recommend(ctx) == original
    assert regular_preference_cards(ctx["regular_preferences"]) == []
    # 더미 모드도 1,000명 시연 주문에서 근거를 찾고, API 모드와 같은 응답 구조를 유지한다.
    dummy_preferences = repo.regular_preferences()
    assert dummy_preferences and all(row["previous_visit"] and row["today_table"] for row in dummy_preferences)
    member = prepare_history(server)
    db = server.app.state.db
    # 테스트 메모리 DB의 과거 주문을 분산시켜 특정 취향을 단정할 수 없는 상황을 만든다.
    for line in db.all("SELECT id FROM order_items WHERE menu_id=? ORDER BY id", ("screen-fish",))[:2]:
        db.run("UPDATE order_items SET menu_id=?, name=? WHERE id=?", ("screen-egg", "DB 계란말이", line["id"]))
    screen = open_recommendations(monkeypatch)
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    assert "주문 기억 손님" in addition and "5번째 방문" in addition
    assert "이전 주문일" not in addition and "오늘 주문: DB 계란말이" in addition
    assert "멘트 예시" in addition and "DB 먹태" not in addition


def test_original_cards_and_pagination_are_preserved_above_added_preferences(server, monkeypatch):
    prepare_history(server)
    screen = open_recommendations(monkeypatch)
    screen.button(key="mk_rerecommend").click().run()  # 추천은 [AI 추천 받기]를 눌러야 만들어진다
    sections = [element.value for element in screen.get("html")]
    original = [html for html in sections if 'class="rec recommendation-card"' in html]
    addition = next(html for html in sections if 'class="recs regular-preferences"' in html)
    assert len(original) == 4
    assert all("주문 기억 손님" not in html for html in original)
    assert "주문 기억 손님" in addition and "80% 이상" in addition
    assert sections.index(original[0]) < sections.index(addition)
    screen.button(key="mk_rerecommend").click().run()
    assert not screen.exception
    sections = [element.value for element in screen.get("html")]
    after = [html for html in sections if 'class="rec recommendation-card"' in html]
    assert after != original
    assert next(html for html in sections if 'class="recs regular-preferences"' in html) == addition


def test_preference_api_failure_does_not_break_original_recommendations(server, monkeypatch):
    import admin_repository as ar
    from pathlib import Path

    screen = open_recommendations(monkeypatch)
    screen.button(key="mk_rerecommend").click().run()  # 추천은 버튼을 눌러야 만들어진다
    original = [element.value for element in screen.get("html")
                if 'class="rec recommendation-card"' in element.value]
    assert original
    ar._loaded_mtime = Path(ar.__file__).stat().st_mtime

    def unavailable(self):
        raise ar.api.ApiUnavailable("테스트용 추가 조회 실패")

    monkeypatch.setattr(ar.AdminRepository, "regular_preferences", unavailable)
    screen.run()
    assert not screen.exception
    assert [element.value for element in screen.get("html")
            if 'class="rec recommendation-card"' in element.value] == original
    assert any("단골 손님 정보를 불러오지 못했어요" in element.value for element in screen.info)


def test_ten_ordering_regulars_are_all_visible_without_truncating(server, monkeypatch):
    """방문 횟수만 확인되는 단골도 빠뜨리지 않고 열 팀 모두 표시하는지 확인한다."""
    db = server.app.state.db
    save_menu(server, "ten-screen", "단골의 오늘 메뉴")
    for index in range(10):
        member = server.app.state.members.upsert_login(f"screen-ten-{index}", f"열 팀 단골 {index}")
        db.run("UPDATE members SET visit_count=? WHERE id=?", (5 + index, member["id"]))
        order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                       (index + 1, member["id"], 14000, datetime.now(timezone.utc).isoformat()))
        db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
               (order, "ten-screen", "단골의 오늘 메뉴", 1, 14000))
    screen = open_recommendations(monkeypatch)
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    for index in range(10):
        assert f"열 팀 단골 {index}님" in addition
        assert f"{5 + index}번째 방문" in addition
    assert addition.count("멘트 예시:") == 10 and "최대 3" not in addition
    assert "이전 주문일" not in addition
    assert "80%" not in addition
    assert addition.count('class="rec"') == 1


def test_varied_regulars_and_one_preference_suggestion_use_separate_cards(server, monkeypatch):
    """80% 손님이 있어도 일반 단골 인사에는 비율 설명 없이 모든 손님을 안내한다."""
    from app.stores.regular_examples import remove_regular_examples, seed_regular_examples

    db = server.app.state.db
    for menu_id, name in (("a1", "먹태"), ("a2", "골뱅이"), ("a4", "계란말이"), ("a8", "파전")):
        save_menu(server, menu_id, name)
    seed_regular_examples(db, datetime.now(KST).date())
    member = server.app.state.members.upsert_login("varied-screen", "여러 메뉴 단골")
    db.run("UPDATE members SET visit_count=8 WHERE id=?", (member["id"],))
    for days, menu_id, name in ((0, "a1", "먹태"), (1, "a2", "골뱅이"),
                                (2, "a4", "계란말이"), (3, "a8", "파전")):
        stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                       (9, member["id"], 14000, stamp))
        db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
               (order, menu_id, name, 1, 14000))
    screen = open_recommendations(monkeypatch)
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    general, favorite = addition.split("자주 드시는 메뉴를 기억하는 인사", 1)
    assert "여러 메뉴 단골님" in general and "8번째 방문" in general
    assert "여러 안주" in general and "80%" not in general
    assert favorite.count("멘트 예시:") == 1 and addition.count("80% 이상") == 1
    # 예시를 실제로 제거한 뒤 고객 화면에서도 사라지고, 일반 단골 인사는 계속 표시된다.
    assert remove_regular_examples(db) == {"restored_members": 3, "restored_orders": 33}
    screen.sidebar.radio(key="nav_sub_고객 등급").set_value("고객 목록").run()
    assert not screen.exception
    assert len(screen.dataframe[0].value) == 1
    assert screen.dataframe[0].value.iloc[0]["닉네임"] == "여러 메뉴 단골"
    screen.sidebar.radio(key="nav_sub_마케팅").set_value("AI 추천").run()
    assert not screen.exception
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    assert "여러 메뉴 단골님" in addition and "80%" not in addition


def test_preview_is_replaced_by_real_regular_greeting_and_changes_with_order(server, monkeypatch):
    """발표용 예정 문구에서 실제 단골 주문에 맞는 응대로 전환되는 흐름을 확인한다."""
    screen = open_recommendations(monkeypatch)
    # 실제 DB(API 모드)에 대상이 없으면 예시 대신 안내만 보여 준다.
    assert any("재방문 고객이 아직 없습니다" in e.value for e in screen.info)
    member = prepare_history(server)
    screen.button(key="mk_rerecommend").click().run()
    assert not screen.exception
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    assert "AI가 이런 인사를 추천할 예정" not in addition
    assert "주문 기억 손님님" in addition and "5번째 방문" in addition
    assert "7번 테이블" in addition and "DB 계란말이" in addition
    path = "/admin/api/marketing/regular-preferences"
    headers = {"Authorization": "Bearer admin-secret"}
    before = server.get(path, headers=headers).json()["preferences"][0]
    assert before["visit_note"] in addition
    # 실제 주문이 바뀌면 예정 문구를 고정하지 않고 새로운 DB 근거로 응대를 제안한다.
    db = server.app.state.db
    order = db.run("INSERT INTO orders (table_no, member_id, total, created_at) VALUES (?, ?, ?, ?)",
                   (7, member["id"], 14000, datetime.now(timezone.utc).isoformat()))
    db.run("INSERT INTO order_items (order_id, menu_id, name, qty, unit_price) VALUES (?, ?, ?, ?, ?)",
           (order, "screen-fish", "DB 먹태", 1, 14000))
    screen.button(key="mk_rerecommend").click().run()
    assert not screen.exception
    after = server.get(path, headers=headers).json()["preferences"][0]
    addition = next(element.value for element in screen.get("html") if 'class="recs regular-preferences"' in element.value)
    assert after["visit_note"] != before["visit_note"]
    assert after["visit_note"] in addition
    assert "AI가 이런 인사를 추천할 예정" not in addition


def test_running_app_reloads_old_marketing_modules_for_preview(server, monkeypatch):
    """기존 서버에 남은 예전 화면·추천 함수 때문에 새 안내가 사라지지 않아야 한다."""
    from admin.marketing import recommendations
    from admin.views import marketing

    monkeypatch.setattr(recommendations, "_loaded_mtime", -1, raising=False)
    monkeypatch.setattr(marketing, "_loaded_mtime", -1, raising=False)
    monkeypatch.delattr(recommendations, "regular_preference_preview_cards")
    monkeypatch.setattr(marketing, "_render_regular_preferences", lambda repo: None)
    screen = open_recommendations(monkeypatch)
    assert not screen.exception
    assert any("재방문 고객이 아직 없습니다" in e.value for e in screen.info)
