import unittest

from streamlit.testing.v1 import AppTest

from ai_quiz_data import QUESTIONS
from menu_data import MENU_BY_ID
from recommendations import recommend_combos

# 질문마다 고른 선택지 번호 (hunger, stress, people, gender, kind, spicy, intent, budget)
PICKS = [1, 2, 2, 0, 2, 1, 1, 1]


class QuizDataTests(unittest.TestCase):
    def test_questions_cover_meeting_notes_in_order(self):
        # 회의록 2.4: 배고픔·스트레스 → 인원수·성비 → 종류·맵기 → 방문 의도 → 예산
        self.assertEqual([q["id"] for q in QUESTIONS],
                         ["hunger", "stress", "people", "gender", "kind", "spicy", "intent", "budget"])
        for q in QUESTIONS:
            self.assertGreaterEqual(len(q["options"]), 3, q["id"])
            self.assertEqual(len({o["value"] for o in q["options"]}), len(q["options"]), q["id"])


class QuizRecommendationTests(unittest.TestCase):
    def test_not_spicy_excludes_every_hot_themed_combo(self):
        names = [c["id"] for c in recommend_combos(2, 100000, "맵지 않게")]
        self.assertTrue(names)
        self.assertFalse({"spicy", "fire", "seafood", "dooroochi"} & set(names))

    def test_budget_is_always_respected_and_results_exist_for_every_budget(self):
        for budget in (30000, 50000, 70000, 100000, 150000):
            for people in (1, 2, 3, 4, 5):
                for combo in recommend_combos(people, budget, hunger="매우 배고파요"):
                    self.assertLessEqual(combo["price"], budget)
        self.assertTrue(recommend_combos(1, 30000))

    def test_kind_and_intent_raise_matching_combos(self):
        base = [c["id"] for c in recommend_combos(2, 100000)]
        noodle = [c["id"] for c in recommend_combos(2, 100000, kind="rice_noodle", intent="가볍게")]
        self.assertIn(noodle[0], ("ramen", "dooroochi"))
        self.assertNotEqual(base, noodle)
        self.assertIn("원하신 밥·면 위주", recommend_combos(2, 100000, kind="rice_noodle")[0]["reason"])

    def test_soup_choice_ranks_a_soup_combo_first_even_when_spicy_is_chosen(self):
        # 짬뽕탕이 든 "얼큰한 해물 조합"은 해산물이면서 탕이다 → 탕·국물 선택이 반영되어야 한다
        top = recommend_combos(3, 70000, "매콤하게", kind="soup", intent="회식")[0]
        self.assertIn(top["id"], ("seafood", "mussel", "soup"))
        self.assertIn("탕·국물 위주", top["reason"])

    def test_hunger_adds_portions(self):
        food = lambda combos, cid: sum(x["qty"] for c in combos if c["id"] == cid for x in c["components"] if x["id"] != "b1")
        normal = recommend_combos(2, 150000, hunger="적당해요")
        hungry = recommend_combos(2, 150000, hunger="매우 배고파요")
        cid = normal[0]["id"]
        self.assertIn(cid, [c["id"] for c in hungry])
        self.assertGreater(food(hungry, cid), food(normal, cid))
        self.assertIn("한 접시 더", hungry[0]["reason"])

    def test_high_stress_prefers_hot_combos(self):
        top = recommend_combos(2, 100000, stress="높음")[0]
        self.assertIn(top["id"], ("spicy", "fire", "seafood", "dooroochi"))
        self.assertIn("칼칼한", top["reason"])

    def test_rain_prefers_spicy_not_the_obvious_pajeon_combo(self):
        rainy = [c["id"] for c in recommend_combos(2, 100000, weather="rain")]
        self.assertNotEqual(rainy[0], "soup")  # 어묵탕+해물파전은 뻔해서 가산하지 않는다
        self.assertTrue({"spicy", "fire", "seafood", "dooroochi"} & set(rainy[:1]))

    def test_late_night_prefers_light_combos(self):
        late = recommend_combos(1, 100000, hour=23)
        self.assertIn("늦은 시간", " ".join(c["reason"] for c in late))

    def test_soldout_and_missing_menu_are_skipped(self):
        menu = {k: dict(v) for k, v in MENU_BY_ID.items()}
        menu["d7"]["soldout"] = True
        del menu["s5"]
        ids = [c["id"] for c in recommend_combos(2, 150000, menu_by_id=menu, kind="rice_noodle")]
        self.assertNotIn("ramen", ids)
        self.assertNotIn("dooroochi", ids)


class QuizScreenTests(unittest.TestCase):
    def open_quiz(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        app.button(key="start_btn").click().run()
        app.button(key="open_quiz").click().run()
        return app

    def test_menu_screen_has_ai_question_button_and_opens_first_question(self):
        app = self.open_quiz()
        self.assertEqual(app.session_state["page"], "ai_quiz")
        self.assertEqual(app.session_state["quiz"]["step"], 0)
        html = " ".join(h.value for h in app.get("html"))
        self.assertIn("지금 얼마나 배고프세요?", html)
        self.assertTrue(app.button(key="quiz_back").disabled)
        picks = [b.key for b in app.button if str(b.key).startswith("quiz_pick_hunger_")]
        self.assertEqual(len(picks), 3)
        self.assertFalse(app.exception)

    def test_each_pick_goes_to_next_question_and_back_keeps_answers(self):
        app = self.open_quiz()
        for step, pick in enumerate(PICKS[:3]):
            q = QUESTIONS[step]
            self.assertIn(q["title"], " ".join(h.value for h in app.get("html")))
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
            self.assertEqual(app.session_state["quiz"]["step"], step + 1)
        app.button(key="quiz_back").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], 2)
        self.assertEqual(app.session_state["quiz"]["answers"]["people"], next(q for q in QUESTIONS if q["id"] == "people")["options"][2]["value"])
        self.assertFalse(app.exception)

    def test_can_jump_between_answered_questions_and_back_to_result(self):
        app = self.open_quiz()
        for q, pick in zip(QUESTIONS[:4], PICKS):
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], 4)
        self.assertTrue(app.button(key="quiz_step_5").disabled)  # 아직 답하지 않은 질문 너머는 막힘
        app.button(key="quiz_step_1").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], 1)
        app.button(key="quiz_step_4").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], 4)
        for q, pick in zip(QUESTIONS[4:], PICKS[4:]):
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], len(QUESTIONS))
        # 결과에서 답변을 눌러 수정하면 다시 결과로
        app.button(key="quiz_review_stress").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], 1)
        app.button(key="quiz_pick_stress_0").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], len(QUESTIONS))
        self.assertEqual(app.session_state["quiz"]["answers"]["stress"], "낮음")
        self.assertFalse(app.exception)

    def test_full_flow_shows_result_and_adds_combo_to_cart(self):
        app = self.open_quiz()
        for q, pick in zip(QUESTIONS, PICKS):
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], len(QUESTIONS))
        html = " ".join(h.value for h in app.get("html"))
        self.assertIn("맞춤 메뉴 조합이 완성됐어요", html)
        self.assertIn("자동 반영", html)
        adds = [b for b in app.button if str(b.key).startswith("add_combo_")]
        self.assertGreaterEqual(len(adds), 1)
        adds[0].click().run()
        line = next(iter(app.session_state["cart"].values()))
        self.assertTrue(line["id"].startswith("combo:"))
        self.assertFalse(app.exception)
        # 처음부터 다시 → 첫 질문
        app.button(key="quiz_restart").click().run()
        self.assertEqual(app.session_state["quiz"], {"step": 0, "answers": {}})
        # 메뉴 보러가기 / 닫기
        app.button(key="quiz_close").click().run()
        self.assertEqual(app.session_state["page"], "menu")

    def test_weather_query_param_is_reflected(self):
        app = AppTest.from_file("app.py", default_timeout=30)
        app.query_params["weather"] = "rain"
        app.run()
        app.button(key="start_btn").click().run()
        app.button(key="open_quiz").click().run()
        for q, pick in zip(QUESTIONS, PICKS):
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
        self.assertIn("날씨 비", " ".join(h.value for h in app.get("html")))

    def test_impossible_budget_offers_to_change_it(self):
        self.assertEqual(recommend_combos(5, 30000, hunger="적당해요", kind="rice_noodle"), [])
        app = self.open_quiz()
        picks = [0, 0, 4, 0, 5, 0, 3, 0]  # 5명 이상 + 3만원 이하
        for q, pick in zip(QUESTIONS, picks):
            app.button(key=f"quiz_pick_{q['id']}_{pick}").click().run()
        self.assertFalse([b for b in app.button if str(b.key).startswith("add_combo_")])
        app.button(key="quiz_edit_budget").click().run()
        self.assertEqual(app.session_state["quiz"]["step"], len(QUESTIONS) - 1)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
